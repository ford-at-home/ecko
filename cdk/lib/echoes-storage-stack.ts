import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

export interface EchoesStorageStackProps extends cdk.StackProps {
  environment: string;
}

export class EchoesStorageStack extends cdk.Stack {
  public readonly audioBucket: s3.Bucket;
  public readonly echoesTable: dynamodb.Table;

  constructor(scope: Construct, id: string, props: EchoesStorageStackProps) {
    super(scope, id, props);

    // S3 Bucket for audio files
    this.audioBucket = new s3.Bucket(this, 'AudioBucket', {
      bucketName: `echoes-audio-${props.environment}-${this.account}`,
      versioned: false,
      publicReadAccess: false,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      lifecycleRules: [
        {
          id: 'DeleteOldVersions',
          expiration: cdk.Duration.days(365), // Keep files for 1 year
          abortIncompleteMultipartUploadAfter: cdk.Duration.days(7),
        },
      ],
      cors: [
        {
          allowedMethods: [
            s3.HttpMethods.GET,
            s3.HttpMethods.POST,
            s3.HttpMethods.PUT,
            s3.HttpMethods.DELETE,
            s3.HttpMethods.HEAD,
          ],
          allowedOrigins: ['*'], // Should be restricted in production
          allowedHeaders: ['*'],
          exposedHeaders: ['ETag'],
          maxAge: 3000,
        },
      ],
      removalPolicy: props.environment === 'prod' 
        ? cdk.RemovalPolicy.RETAIN 
        : cdk.RemovalPolicy.DESTROY,
    });

    // DynamoDB Table for echo metadata
    this.echoesTable = new dynamodb.Table(this, 'EchoesTable', {
      tableName: `EchoesTable-${props.environment}`,
      partitionKey: {
        name: 'userId',
        type: dynamodb.AttributeType.STRING,
      },
      sortKey: {
        name: 'echoId',
        type: dynamodb.AttributeType.STRING,
      },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      encryption: dynamodb.TableEncryption.AWS_MANAGED,
      pointInTimeRecovery: props.environment === 'prod',
      removalPolicy: props.environment === 'prod' 
        ? cdk.RemovalPolicy.RETAIN 
        : cdk.RemovalPolicy.DESTROY,
    });

    // Global Secondary Index for emotion-based queries
    this.echoesTable.addGlobalSecondaryIndex({
      indexName: 'emotion-timestamp-index',
      partitionKey: {
        name: 'emotion',
        type: dynamodb.AttributeType.STRING,
      },
      sortKey: {
        name: 'timestamp',
        type: dynamodb.AttributeType.STRING,
      },
    });

    // Create IAM role for user-scoped S3 access
    const userS3AccessRole = new iam.Role(this, 'UserS3AccessRole', {
      assumedBy: new iam.FederatedPrincipal(
        'cognito-identity.amazonaws.com',
        {
          StringEquals: {
            'cognito-identity.amazonaws.com:aud': '${cognito-identity-pool-id}', // Will be replaced
          },
          'ForAnyValue:StringLike': {
            'cognito-identity.amazonaws.com:amr': 'authenticated',
          },
        },
        'sts:AssumeRoleWithWebIdentity'
      ),
      description: 'Role for authenticated users to access S3 audio files',
    });

    // Policy for user-scoped S3 access
    userS3AccessRole.addToPolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: [
        's3:GetObject',
        's3:PutObject',
        's3:DeleteObject',
      ],
      resources: [
        this.audioBucket.arnForObjects('${cognito-identity.amazonaws.com:sub}/*'),
      ],
    }));

    userS3AccessRole.addToPolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: [
        's3:ListBucket',
      ],
      resources: [this.audioBucket.bucketArn],
      conditions: {
        StringLike: {
          's3:prefix': ['${cognito-identity.amazonaws.com:sub}/*'],
        },
      },
    }));

    // Output important values
    new cdk.CfnOutput(this, 'AudioBucketName', {
      value: this.audioBucket.bucketName,
      description: 'S3 bucket for audio files',
      exportName: `${props.environment}-AudioBucketName`,
    });

    new cdk.CfnOutput(this, 'AudioBucketArn', {
      value: this.audioBucket.bucketArn,
      description: 'S3 bucket ARN',
      exportName: `${props.environment}-AudioBucketArn`,
    });

    new cdk.CfnOutput(this, 'EchoesTableName', {
      value: this.echoesTable.tableName,
      description: 'DynamoDB table for echo metadata',
      exportName: `${props.environment}-EchoesTableName`,
    });

    new cdk.CfnOutput(this, 'EchoesTableArn', {
      value: this.echoesTable.tableArn,
      description: 'DynamoDB table ARN',
      exportName: `${props.environment}-EchoesTableArn`,
    });

    new cdk.CfnOutput(this, 'UserS3AccessRoleArn', {
      value: userS3AccessRole.roleArn,
      description: 'IAM role for user S3 access',
      exportName: `${props.environment}-UserS3AccessRoleArn`,
    });
  }
}