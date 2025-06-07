"""CDK stack for the newcdkproject.

This stack defines core resources used by the AI Certification Study Assistant
(AWS Beacon). Resources include an S3 bucket to store study materials,
an OpenSearch Serverless collection for vector search, and an IAM role for
future Lambda functions that will interact with these services.
"""

from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_s3 as s3,
    aws_opensearchserverless as oss,
    aws_lambda as _lambda,
    aws_events as events,
    aws_events_targets as targets,
    aws_logs as logs,
    aws_iam as iam,
)
import json
from constructs import Construct

class NewcdkprojectStack(Stack):
    """Main CDK stack defining the infrastructure resources."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ------------------------------------------------------------------
        # 1. S3 bucket to store certification materials
        # ------------------------------------------------------------------
        bucket = s3.Bucket(
            self,
            "CertificationMaterialsBucket",
            bucket_name="certification-study-materials-will-dev",
            versioned=True,  # retain previous versions of objects
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
        )

        # ------------------------------------------------------------------
        # 2. IAM role for Lambda functions
        # ------------------------------------------------------------------
        lambda_role = iam.Role(
            self,
            "LambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
        )

        # Allow read-only access to the S3 bucket
        bucket.grant_read(lambda_role)

        # Additional permissions for OpenSearch and Bedrock
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["aoss:APIAccessAll"],
                resources=["*"]
            )
        )
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=["arn:aws:bedrock:*::foundation-model/amazon.titan-embed-text-v1"],
            )
        )

        # ------------------------------------------------------------------
        # 3. OpenSearch Serverless collection for RAG embeddings
        # ------------------------------------------------------------------
        collection_name = "certification-rag-collection"

        # Encryption policy required for the collection
        encryption_policy = oss.CfnSecurityPolicy(
            self,
            "RagEncryptionPolicy",
            name="rag-encryption-policy",
            type="encryption",
            policy=json.dumps(
                {
                    "Rules": [
                        {
                            "ResourceType": "collection",
                            "Resource": [f"collection/{collection_name}"],
                        }
                    ],
                    "AWSOwnedKey": True,
                }
            ),
        )

        # Network policy allowing public access to the collection
        network_policy = oss.CfnSecurityPolicy(
            self,
            "RagNetworkPolicy",
            name="rag-network-policy",
            type="network",
            policy=json.dumps(
                [
                    {
                        "Description": "Public access",
                        "Rules": [
                            {
                                "ResourceType": "collection",
                                "Resource": [f"collection/{collection_name}"],
                            },
                            {
                                "ResourceType": "dashboard",
                                "Resource": [f"collection/{collection_name}"],
                            },
                        ],
                        "AllowFromPublic": True,
                    }
                ]
            ),
        )

        collection = oss.CfnCollection(
            self,
            "RagCollection",
            name=collection_name,
            type="VECTORSEARCH",
        )

        # Ensure policies are created before the collection
        collection.add_dependency(encryption_policy)
        collection.add_dependency(network_policy)

        # Access policy so the Lambda role can write to the embeddings index
        # The index itself will be created on demand when data is written.
        access_policy = oss.CfnAccessPolicy(
            self,
            "LambdaAccessPolicy",
            name="lambda-access-policy",
            type="data",
            policy=json.dumps(
                [
                    {
                        "Description": "Lambda access to embeddings index",
                        "Rules": [
                            {
                                "ResourceType": "index",
                                "Resource": [
                                    f"index/{collection_name}/cert-embeddings",
                                ],
                                "Permission": [
                                    "aoss:CreateIndex",
                                    "aoss:WriteDocument",
                                    "aoss:ReadDocument",
                                    "aoss:DescribeIndex",
                                ],
                            }
                        ],
                        "Principal": [lambda_role.role_arn],
                    }
                ],
                separators=(",", ":"),
            ),
        )
        access_policy.add_dependency(collection)

        # ------------------------------------------------------------------
        # 4. Lambda function to ingest study materials
        # ------------------------------------------------------------------
        ingest_lambda = _lambda.Function(
            self,
            "IngestStudyMaterialFunction",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="ingest_study_material.handler",
            code=_lambda.Code.from_asset("lambda_functions"),
            timeout=Duration.seconds(60),
            memory_size=512,
            role=lambda_role,
            function_name="IngestStudyMaterialFunction",
        )

        log_group = logs.LogGroup(
            self,
            "IngestStudyMaterialLogGroup",
            log_group_name=f"/aws/lambda/{ingest_lambda.function_name}",
            removal_policy=RemovalPolicy.DESTROY,
        )

        # EventBridge rule for S3 uploads
        rule = events.Rule(
            self,
            "S3IngestRule",
            event_pattern=events.EventPattern(
                source=["aws.s3"],
                detail_type=["Object Created"],
                detail={"bucket": {"name": [bucket.bucket_name]}},
            ),
        )

        rule.add_target(targets.LambdaFunction(ingest_lambda))

        # ------------------------------------------------------------------
        # Outputs for easy reference
        # ------------------------------------------------------------------
        self.bucket_name = bucket.bucket_name
        self.collection_name = collection.name
        self.lambda_role_arn = lambda_role.role_arn
        self.ingest_lambda_name = ingest_lambda.function_name
        self.log_group_name = log_group.log_group_name
        self.s3_rule_name = rule.rule_name

        self.add_output("BucketName", self.bucket_name)
        self.add_output("CollectionName", self.collection_name)
        self.add_output("LambdaRoleArn", self.lambda_role_arn)
        self.add_output("IngestLambdaName", self.ingest_lambda_name)
        self.add_output("IngestLambdaLogGroup", self.log_group_name)
        self.add_output("S3EventRule", self.s3_rule_name)

    # Helper to add outputs with consistent naming
    def add_output(self, id_: str, value: str) -> None:
        from aws_cdk import CfnOutput

        CfnOutput(self, id_, value=value)
