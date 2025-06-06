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

        # ------------------------------------------------------------------
        # 3. OpenSearch Serverless collection for RAG embeddings
        # ------------------------------------------------------------------
        collection = oss.CfnCollection(
            self,
            "RagCollection",
            name="certification-rag-collection",
            type="VECTORSEARCH",
        )

        # OpenSearch index for embeddings
        index = oss.CfnIndex(
            self,
            "CertEmbeddingsIndex",
            collection_endpoint=collection.attr_collection_endpoint,
            index_name="cert-embeddings",
        )

        # Access policy so the Lambda role can write to the index
        access_policy = oss.CfnAccessPolicy(
            self,
            "LambdaAccessPolicy",
            name="lambda-access-policy",
            type="data",
            policy=json.dumps(
                {
                    "Rules": [
                        {
                            "Resource": [
                                f"collection/{collection.name}",
                                f"index/{collection.name}/cert-embeddings",
                            ],
                            "Permission": [
                                "aoss:DescribeCollection",
                                "aoss:WriteDocument",
                                "aoss:ReadDocument",
                                "aoss:CreateIndex",
                            ],
                        }
                    ],
                    "Principal": [lambda_role.role_arn],
                }
            ),
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
