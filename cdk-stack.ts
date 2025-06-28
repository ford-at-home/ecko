import * as cdk from 'aws-cdk-lib';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as kms from 'aws-cdk-lib/aws-kms';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

export interface EchoesStackProps extends cdk.StackProps {
  environment: 'dev' | 'staging' | 'prod';
  billingMode?: dynamodb.BillingMode;
  readCapacity?: number;
  writeCapacity?: number;
}

export class EchoesStack extends cdk.Stack {
  public readonly table: dynamodb.Table;
  public readonly kmsKey?: kms.Key;
  
  constructor(scope: Construct, id: string, props: EchoesStackProps) {
    super(scope, id, props);

    const { environment, billingMode = dynamodb.BillingMode.PAY_PER_REQUEST } = props;
    const isProduction = environment === 'prod';
    const isProvisioned = billingMode === dynamodb.BillingMode.PROVISIONED;

    // KMS Key for production encryption
    if (isProduction) {
      this.kmsKey = new kms.Key(this, 'EchoesKMSKey', {
        description: 'KMS Key for Echoes DynamoDB Table encryption',
        alias: `echoes-${environment}`,
        policy: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              sid: 'EnableIAMUserPermissions',
              effect: iam.Effect.ALLOW,
              principals: [new iam.AccountRootPrincipal()],
              actions: ['kms:*'],
              resources: ['*'],
            }),
            new iam.PolicyStatement({
              sid: 'AllowDynamoDBService',
              effect: iam.Effect.ALLOW,
              principals: [new iam.ServicePrincipal('dynamodb.amazonaws.com')],
              actions: ['kms:Decrypt', 'kms:GenerateDataKey'],
              resources: ['*'],
            }),
          ],
        }),
      });
    }

    // Main DynamoDB Table
    this.table = new dynamodb.Table(this, 'EchoesTable', {
      tableName: `EchoesTable-${environment}`,
      billingMode,
      
      // Primary Key
      partitionKey: {
        name: 'userId',
        type: dynamodb.AttributeType.STRING,
      },
      sortKey: {
        name: 'timestamp',
        type: dynamodb.AttributeType.STRING,
      },

      // Capacity settings (only for provisioned mode)
      ...(isProvisioned && {
        readCapacity: props.readCapacity || 100,
        writeCapacity: props.writeCapacity || 100,
      }),

      // Advanced features
      stream: dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
      timeToLiveAttribute: 'ttl',
      pointInTimeRecovery: isProduction,
      
      // Encryption
      encryption: isProduction 
        ? dynamodb.TableEncryption.CUSTOMER_MANAGED
        : dynamodb.TableEncryption.AWS_MANAGED,
      encryptionKey: this.kmsKey,

      // Deletion protection for production
      removalPolicy: isProduction 
        ? cdk.RemovalPolicy.RETAIN 
        : cdk.RemovalPolicy.DESTROY,

      // Tags
      tags: {
        Environment: environment,
        Application: 'Echoes',
        Component: 'Database',
        ManagedBy: 'CDK',
      },
    });

    // Global Secondary Indexes
    this.addGlobalSecondaryIndexes(isProvisioned, props);
    
    // Auto Scaling (only for provisioned mode)
    if (isProvisioned) {
      this.setupAutoScaling();
    }

    // CloudWatch Alarms
    this.setupCloudWatchAlarms();

    // Outputs
    this.createOutputs();
  }

  private addGlobalSecondaryIndexes(isProvisioned: boolean, props: EchoesStackProps) {
    const gsiProps = isProvisioned ? {
      readCapacity: props.readCapacity || 100,
      writeCapacity: props.writeCapacity || 100,
    } : {};

    // GSI 1: Emotion-Timestamp Index
    this.table.addGlobalSecondaryIndex({
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
      ...gsiProps,
    });

    // GSI 2: EchoId Index
    this.table.addGlobalSecondaryIndex({
      indexName: 'echoId-index',
      partitionKey: {
        name: 'echoId',
        type: dynamodb.AttributeType.STRING,
      },
      projectionType: dynamodb.ProjectionType.ALL,
      ...gsiProps,
    });

    // GSI 3: User-Emotion Index
    this.table.addGlobalSecondaryIndex({
      indexName: 'userId-emotion-index',
      partitionKey: {
        name: 'userId',
        type: dynamodb.AttributeType.STRING,
      },
      sortKey: {
        name: 'emotion',
        type: dynamodb.AttributeType.STRING,
      },
      projectionType: dynamodb.ProjectionType.INCLUDE,
      nonKeyAttributes: [
        'timestamp',
        'echoId', 
        's3Url',
        'location',
        'tags',
        'detectedMood',
        'transcript',
        'metadata'
      ],
      ...gsiProps,
    });
  }

  private setupAutoScaling() {
    // Enable auto scaling for the table
    const readScaling = this.table.autoScaleReadCapacity({
      minCapacity: 5,
      maxCapacity: 4000,
    });

    const writeScaling = this.table.autoScaleWriteCapacity({
      minCapacity: 5,
      maxCapacity: 4000,
    });

    // Target tracking scaling policies
    readScaling.scaleOnUtilization({
      targetUtilizationPercent: 70,
      scaleInCooldown: cdk.Duration.minutes(5),
      scaleOutCooldown: cdk.Duration.minutes(1),
    });

    writeScaling.scaleOnUtilization({
      targetUtilizationPercent: 70,
      scaleInCooldown: cdk.Duration.minutes(5),
      scaleOutCooldown: cdk.Duration.minutes(1),
    });

    // Auto scaling for GSIs
    const gsiNames = ['emotion-timestamp-index', 'echoId-index', 'userId-emotion-index'];
    
    gsiNames.forEach(gsiName => {
      const gsiReadScaling = this.table.autoScaleGlobalSecondaryIndexReadCapacity(gsiName, {
        minCapacity: 5,
        maxCapacity: 4000,
      });

      const gsiWriteScaling = this.table.autoScaleGlobalSecondaryIndexWriteCapacity(gsiName, {
        minCapacity: 5,
        maxCapacity: 4000,
      });

      gsiReadScaling.scaleOnUtilization({
        targetUtilizationPercent: 70,
        scaleInCooldown: cdk.Duration.minutes(5),
        scaleOutCooldown: cdk.Duration.minutes(1),
      });

      gsiWriteScaling.scaleOnUtilization({
        targetUtilizationPercent: 70,
        scaleInCooldown: cdk.Duration.minutes(5),
        scaleOutCooldown: cdk.Duration.minutes(1),
      });
    });
  }

  private setupCloudWatchAlarms() {
    // SNS Topics for alerts
    const alertsTopic = new sns.Topic(this, 'EchoesAlerts', {
      topicName: `echoes-alerts-${this.node.tryGetContext('environment')}`,
      displayName: 'Echoes Application Alerts',
    });

    const criticalTopic = new sns.Topic(this, 'EchoesCritical', {
      topicName: `echoes-critical-${this.node.tryGetContext('environment')}`,
      displayName: 'Echoes Critical Alerts',
    });

    // High Latency Alarm
    new cloudwatch.Alarm(this, 'HighLatencyAlarm', {
      alarmName: `${this.table.tableName}-HighLatency`,
      alarmDescription: 'DynamoDB table has high query latency',
      metric: new cloudwatch.Metric({
        namespace: 'AWS/DynamoDB',
        metricName: 'SuccessfulRequestLatency',
        dimensionsMap: {
          TableName: this.table.tableName,
          Operation: 'Query',
        },
        statistic: 'Average',
        period: cdk.Duration.minutes(5),
      }),
      threshold: 100,
      evaluationPeriods: 2,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
    }).addAlarmAction(new cloudwatch.SnsAction(alertsTopic));

    // Throttling Alarm
    new cloudwatch.Alarm(this, 'ThrottlingAlarm', {
      alarmName: `${this.table.tableName}-Throttling`,
      alarmDescription: 'DynamoDB table is experiencing throttling',
      metric: new cloudwatch.Metric({
        namespace: 'AWS/DynamoDB',
        metricName: 'ReadThrottledRequests',
        dimensionsMap: {
          TableName: this.table.tableName,
        },
        statistic: 'Sum',
        period: cdk.Duration.minutes(5),
      }),
      threshold: 0,
      evaluationPeriods: 1,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
    }).addAlarmAction(new cloudwatch.SnsAction(criticalTopic));

    // High Error Rate Alarm
    new cloudwatch.Alarm(this, 'HighErrorRateAlarm', {
      alarmName: `${this.table.tableName}-HighErrorRate`,
      alarmDescription: 'DynamoDB table has high error rate',
      metric: new cloudwatch.Metric({
        namespace: 'AWS/DynamoDB',
        metricName: 'SystemErrors',
        dimensionsMap: {
          TableName: this.table.tableName,
        },
        statistic: 'Sum',
        period: cdk.Duration.minutes(5),
      }),
      threshold: 10,
      evaluationPeriods: 2,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
    }).addAlarmAction(new cloudwatch.SnsAction(criticalTopic));

    // Capacity Utilization Alarms (for provisioned mode)
    if (this.table.billingMode === dynamodb.BillingMode.PROVISIONED) {
      new cloudwatch.Alarm(this, 'HighReadCapacityAlarm', {
        alarmName: `${this.table.tableName}-HighReadCapacity`,
        alarmDescription: 'DynamoDB table read capacity utilization is high',
        metric: new cloudwatch.Metric({
          namespace: 'AWS/DynamoDB',
          metricName: 'ConsumedReadCapacityUnits',
          dimensionsMap: {
            TableName: this.table.tableName,
          },
          statistic: 'Sum',
          period: cdk.Duration.minutes(5),
        }),
        threshold: 80, // 80% of provisioned capacity
        evaluationPeriods: 2,
        comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      }).addAlarmAction(new cloudwatch.SnsAction(alertsTopic));
    }
  }

  private createOutputs() {
    new cdk.CfnOutput(this, 'TableName', {
      value: this.table.tableName,
      description: 'Name of the DynamoDB table',
      exportName: `${this.stackName}-TableName`,
    });

    new cdk.CfnOutput(this, 'TableArn', {
      value: this.table.tableArn,
      description: 'ARN of the DynamoDB table',
      exportName: `${this.stackName}-TableArn`,
    });

    new cdk.CfnOutput(this, 'StreamArn', {
      value: this.table.tableStreamArn!,
      description: 'ARN of the DynamoDB stream',
      exportName: `${this.stackName}-StreamArn`,
    });

    new cdk.CfnOutput(this, 'EmotionTimestampIndex', {
      value: 'emotion-timestamp-index',
      description: 'Name of the emotion-timestamp GSI',
      exportName: `${this.stackName}-EmotionTimestampIndex`,
    });

    new cdk.CfnOutput(this, 'EchoIdIndex', {
      value: 'echoId-index',
      description: 'Name of the echoId GSI',
      exportName: `${this.stackName}-EchoIdIndex`,
    });

    new cdk.CfnOutput(this, 'UserEmotionIndex', {
      value: 'userId-emotion-index',
      description: 'Name of the userId-emotion GSI',
      exportName: `${this.stackName}-UserEmotionIndex`,
    });

    if (this.kmsKey) {
      new cdk.CfnOutput(this, 'KMSKeyId', {
        value: this.kmsKey.keyId,
        description: 'KMS Key ID for encryption',
        exportName: `${this.stackName}-KMSKeyId`,
      });
    }
  }
}

// Usage example
export class EchoesApp extends cdk.App {
  constructor() {
    super();

    const environment = this.node.tryGetContext('environment') || 'dev';
    
    // Development stack
    if (environment === 'dev') {
      new EchoesStack(this, 'EchoesDevStack', {
        environment: 'dev',
        billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
        env: {
          account: process.env.CDK_DEFAULT_ACCOUNT,
          region: process.env.CDK_DEFAULT_REGION,
        },
      });
    }

    // Staging stack
    if (environment === 'staging') {
      new EchoesStack(this, 'EchoesStagingStack', {
        environment: 'staging',
        billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
        env: {
          account: process.env.CDK_DEFAULT_ACCOUNT,
          region: process.env.CDK_DEFAULT_REGION,
        },
      });
    }

    // Production stack
    if (environment === 'prod') {
      new EchoesStack(this, 'EchoesProdStack', {
        environment: 'prod',
        billingMode: dynamodb.BillingMode.PROVISIONED,
        readCapacity: 500,
        writeCapacity: 200,
        env: {
          account: process.env.CDK_DEFAULT_ACCOUNT,
          region: process.env.CDK_DEFAULT_REGION,
        },
      });
    }
  }
}

// Multi-region deployment for global applications
export class EchoesGlobalApp extends cdk.App {
  constructor() {
    super();

    const environment = this.node.tryGetContext('environment') || 'prod';
    
    if (environment === 'prod') {
      // Primary region (US East 1)
      new EchoesStack(this, 'EchoesProdStackUSEast1', {
        environment: 'prod',
        billingMode: dynamodb.BillingMode.PROVISIONED,
        readCapacity: 1000,
        writeCapacity: 400,
        env: {
          account: process.env.CDK_DEFAULT_ACCOUNT,
          region: 'us-east-1',
        },
      });

      // Europe region
      new EchoesStack(this, 'EchoesProdStackEUWest1', {
        environment: 'prod',
        billingMode: dynamodb.BillingMode.PROVISIONED,
        readCapacity: 500,
        writeCapacity: 200,
        env: {
          account: process.env.CDK_DEFAULT_ACCOUNT,
          region: 'eu-west-1',
        },
      });

      // Asia Pacific region
      new EchoesStack(this, 'EchoesProdStackAPSoutheast1', {
        environment: 'prod',
        billingMode: dynamodb.BillingMode.PROVISIONED,
        readCapacity: 300,
        writeCapacity: 100,
        env: {
          account: process.env.CDK_DEFAULT_ACCOUNT,
          region: 'ap-southeast-1',
        },
      });
    }
  }
}

// Export for direct usage
const app = new EchoesApp();
export default app;