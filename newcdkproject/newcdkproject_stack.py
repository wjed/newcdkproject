"""CDK stack for the newcdkproject.

This stack defines core resources used by the AI Certification Study Assistant
(AWS Beacon). Resources include an S3 bucket to store study materials,
an OpenSearch Serverless collection for vector search, and an IAM role for
future Lambda functions that will interact with these services.
"""

from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_opensearchserverless as oss,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_s3_notifications as s3n,
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

        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=["arn:aws:logs:*:*:*"],
            )
        )

        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=["*"]
            )
        )

        # Allow read-only access to the S3 bucket
        bucket.grant_read(lambda_role)

        # ------------------------------------------------------------------
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
        # Lambda function triggered on object uploads
        # ------------------------------------------------------------------
        ingest_lambda = _lambda.Function(
            self,
            "IngestStudyMaterialFunction",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="ingest_study_material.handler",
            code=_lambda.Code.from_asset("lambda_functions"),
            role=lambda_role,
            environment={
                "OPENSEARCH_ENDPOINT": collection.attr_collection_endpoint,
            },
        )

        bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(ingest_lambda),
        )

        # ------------------------------------------------------------------
        # Outputs for easy reference
        # ------------------------------------------------------------------
        self.bucket_name = bucket.bucket_name
        self.collection_name = collection.name
        self.lambda_role_arn = lambda_role.role_arn

        self.add_output("BucketName", self.bucket_name)
        self.add_output("CollectionName", self.collection_name)
        self.add_output("LambdaRoleArn", self.lambda_role_arn)

    # Helper to add outputs with consistent naming
    def add_output(self, id_: str, value: str) -> None:
        from aws_cdk import CfnOutput

        CfnOutput(self, id_, value=value)
