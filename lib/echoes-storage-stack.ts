import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

interface EchoesStorageStackProps extends cdk.StackProps {
  environment: string;
}

export class EchoesStorageStack extends cdk.Stack {
  public readonly audiosBucket: s3.Bucket;
  public readonly echoesTable: dynamodb.Table;

  constructor(scope: Construct, id: string, props: EchoesStorageStackProps) {
    super(scope, id, props);

    const { environment } = props;

    // S3 Bucket for audio files
    this.audiosBucket = new s3.Bucket(this, 'AudiosBucket', {
      bucketName: `echoes-audio-${environment}`,
      versioned: false,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: environment === 'prod' ? cdk.RemovalPolicy.RETAIN : cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: environment !== 'prod',
      cors: [
        {
          allowedMethods: [
            s3.HttpMethods.GET,
            s3.HttpMethods.POST,
            s3.HttpMethods.PUT,
            s3.HttpMethods.DELETE,
          ],
          allowedOrigins: ['*'], // In production, replace with your frontend URLs
          allowedHeaders: ['*'],
          exposedHeaders: ['ETag'],
          maxAge: 3000,
        },
      ],
      lifecycleRules: [
        {
          id: 'DeleteIncompleteMultipartUploads',
          abortIncompleteMultipartUploadAfter: cdk.Duration.days(1),
        },
        {
          id: 'TransitionToIA',
          transitions: [
            {
              storageClass: s3.StorageClass.INFREQUENT_ACCESS,
              transitionAfter: cdk.Duration.days(30),
            },
          ],
        },
      ],
    });

    // DynamoDB Table for echo metadata
    this.echoesTable = new dynamodb.Table(this, 'EchoesTable', {
      tableName: `EchoesTable-${environment}`,
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
      pointInTimeRecovery: environment === 'prod',
      removalPolicy: environment === 'prod' ? cdk.RemovalPolicy.RETAIN : cdk.RemovalPolicy.DESTROY,
      stream: dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
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
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // GSI for user-emotion queries
    this.echoesTable.addGlobalSecondaryIndex({
      indexName: 'userId-emotion-index',
      partitionKey: {
        name: 'userId',
        type: dynamodb.AttributeType.STRING,
      },
      sortKey: {
        name: 'emotion',
        type: dynamodb.AttributeType.STRING,
      },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // Add tags to resources
    cdk.Tags.of(this.audiosBucket).add('Component', 'Storage');
    cdk.Tags.of(this.audiosBucket).add('DataType', 'Audio');
    cdk.Tags.of(this.echoesTable).add('Component', 'Storage');
    cdk.Tags.of(this.echoesTable).add('DataType', 'Metadata');

    // CloudWatch alarms for monitoring
    const bucketSizeAlarm = new cdk.aws_cloudwatch.Alarm(this, 'BucketSizeAlarm', {
      metric: this.audiosBucket.metricBucketSizeBytes(),
      threshold: 10 * 1024 * 1024 * 1024, // 10GB
      evaluationPeriods: 2,
      alarmDescription: 'Audio bucket size exceeds 10GB',
    });

    const tableReadThrottleAlarm = new cdk.aws_cloudwatch.Alarm(this, 'TableReadThrottleAlarm', {
      metric: this.echoesTable.metricThrottledRequestsForOperations({
        operations: [dynamodb.Operation.READ],
      }),
      threshold: 10,
      evaluationPeriods: 2,
      alarmDescription: 'DynamoDB table read requests are being throttled',
    });

    const tableWriteThrottleAlarm = new cdk.aws_cloudwatch.Alarm(this, 'TableWriteThrottleAlarm', {
      metric: this.echoesTable.metricThrottledRequestsForOperations({
        operations: [dynamodb.Operation.WRITE],
      }),
      threshold: 10,
      evaluationPeriods: 2,
      alarmDescription: 'DynamoDB table write requests are being throttled',
    });
  }
}