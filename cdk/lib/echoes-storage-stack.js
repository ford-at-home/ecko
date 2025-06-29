"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.EchoesStorageStack = void 0;
const cdk = require("aws-cdk-lib");
const s3 = require("aws-cdk-lib/aws-s3");
const dynamodb = require("aws-cdk-lib/aws-dynamodb");
const iam = require("aws-cdk-lib/aws-iam");
class EchoesStorageStack extends cdk.Stack {
    constructor(scope, id, props) {
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
                    expiration: cdk.Duration.days(365),
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
                    allowedOrigins: ['*'],
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
            assumedBy: new iam.FederatedPrincipal('cognito-identity.amazonaws.com', {
                StringEquals: {
                    'cognito-identity.amazonaws.com:aud': '${cognito-identity-pool-id}', // Will be replaced
                },
                'ForAnyValue:StringLike': {
                    'cognito-identity.amazonaws.com:amr': 'authenticated',
                },
            }, 'sts:AssumeRoleWithWebIdentity'),
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
exports.EchoesStorageStack = EchoesStorageStack;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZWNob2VzLXN0b3JhZ2Utc3RhY2suanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJlY2hvZXMtc3RvcmFnZS1zdGFjay50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7QUFBQSxtQ0FBbUM7QUFDbkMseUNBQXlDO0FBQ3pDLHFEQUFxRDtBQUNyRCwyQ0FBMkM7QUFPM0MsTUFBYSxrQkFBbUIsU0FBUSxHQUFHLENBQUMsS0FBSztJQUkvQyxZQUFZLEtBQWdCLEVBQUUsRUFBVSxFQUFFLEtBQThCO1FBQ3RFLEtBQUssQ0FBQyxLQUFLLEVBQUUsRUFBRSxFQUFFLEtBQUssQ0FBQyxDQUFDO1FBRXhCLDRCQUE0QjtRQUM1QixJQUFJLENBQUMsV0FBVyxHQUFHLElBQUksRUFBRSxDQUFDLE1BQU0sQ0FBQyxJQUFJLEVBQUUsYUFBYSxFQUFFO1lBQ3BELFVBQVUsRUFBRSxnQkFBZ0IsS0FBSyxDQUFDLFdBQVcsSUFBSSxJQUFJLENBQUMsT0FBTyxFQUFFO1lBQy9ELFNBQVMsRUFBRSxLQUFLO1lBQ2hCLGdCQUFnQixFQUFFLEtBQUs7WUFDdkIsaUJBQWlCLEVBQUUsRUFBRSxDQUFDLGlCQUFpQixDQUFDLFNBQVM7WUFDakQsVUFBVSxFQUFFLEVBQUUsQ0FBQyxnQkFBZ0IsQ0FBQyxVQUFVO1lBQzFDLGNBQWMsRUFBRTtnQkFDZDtvQkFDRSxFQUFFLEVBQUUsbUJBQW1CO29CQUN2QixVQUFVLEVBQUUsR0FBRyxDQUFDLFFBQVEsQ0FBQyxJQUFJLENBQUMsR0FBRyxDQUFDO29CQUNsQyxtQ0FBbUMsRUFBRSxHQUFHLENBQUMsUUFBUSxDQUFDLElBQUksQ0FBQyxDQUFDLENBQUM7aUJBQzFEO2FBQ0Y7WUFDRCxJQUFJLEVBQUU7Z0JBQ0o7b0JBQ0UsY0FBYyxFQUFFO3dCQUNkLEVBQUUsQ0FBQyxXQUFXLENBQUMsR0FBRzt3QkFDbEIsRUFBRSxDQUFDLFdBQVcsQ0FBQyxJQUFJO3dCQUNuQixFQUFFLENBQUMsV0FBVyxDQUFDLEdBQUc7d0JBQ2xCLEVBQUUs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QUFDLFNBQVMsQ0FBQyxJQUFJLEVBQUUscUJBQXFCLEVBQUU7WUFDN0MsS0FBSyxFQUFFLGdCQUFnQixDQUFDLE9BQU87WUFDL0IsV0FBVyxFQUFFLDZCQUE2QjtZQUMxQyxVQUFVLEVBQUUsR0FBRyxLQUFLLENBQUMsV0FBVyxzQkFBc0I7U0FDdkQsQ0FBQyxDQUFDO0lBQ0wsQ0FBQztDQUNGO0FBbkpELGdEQW1KQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCAqIGFzIGNkayBmcm9tICdhd3MtY2RrLWxpYic7XG5pbXBvcnQgKiBhcyBzMyBmcm9tICdhd3MtY2RrLWxpYi9hd3MtczMnO1xuaW1wb3J0ICogYXMgZHluYW1vZGIgZnJvbSAnYXdzLWNkay1saWIvYXdzLWR5bmFtb2RiJztcbmltcG9ydCAqIGFzIGlhbSBmcm9tICdhd3MtY2RrLWxpYi9hd3MtaWFtJztcbmltcG9ydCB7IENvbnN0cnVjdCB9IGZyb20gJ2NvbnN0cnVjdHMnO1xuXG5leHBvcnQgaW50ZXJmYWNlIEVjaG9lc1N0b3JhZ2VTdGFja1Byb3BzIGV4dGVuZHMgY2RrLlN0YWNrUHJvcHMge1xuICBlbnZpcm9ubWVudDogc3RyaW5nO1xufVxuXG5leHBvcnQgY2xhc3MgRWNob2VzU3RvcmFnZVN0YWNrIGV4dGVuZHMgY2RrLlN0YWNrIHtcbiAgcHVibGljIHJlYWRvbmx5IGF1ZGlvQnVja2V0OiBzMy5CdWNrZXQ7XG4gIHB1YmxpYyByZWFkb25seSBlY2hvZXNUYWJsZTogZHluYW1vZGIuVGFibGU7XG5cbiAgY29uc3RydWN0b3Ioc2NvcGU6IENvbnN0cnVjdCwgaWQ6IHN0cmluZywgcHJvcHM6IEVjaG9lc1N0b3JhZ2VTdGFja1Byb3BzKSB7XG4gICAgc3VwZXIoc2NvcGUsIGlkLCBwcm9wcyk7XG5cbiAgICAvLyBTMyBCdWNrZXQgZm9yIGF1ZGlvIGZpbGVzXG4gICAgdGhpcy5hdWRpb0J1Y2tldCA9IG5ldyBzMy5CdWNrZXQodGhpcywgJ0F1ZGlvQnVja2V0Jywge1xuICAgICAgYnVja2V0TmFtZTogYGVjaG9lcy1hdWRpby0ke3Byb3BzLmVudmlyb25tZW50fS0ke3RoaXMuYWNjb3VudH1gLFxuICAgICAgdmVyc2lvbmVkOiBmYWxzZSxcbiAgICAgIHB1YmxpY1JlYWRBY2Nlc3M6IGZhbHNlLFxuICAgICAgYmxvY2tQdWJsaWNBY2Nlc3M6IHMzLkJsb2NrUHVibGljQWNjZXNzLkJMT0NLX0FMTCxcbiAgICAgIGVuY3J5cHRpb246IHMzLkJ1Y2tldEVuY3J5cHRpb24uUzNfTUFOQUdFRCxcbiAgICAgIGxpZmVjeWNsZVJ1bGVzOiBbXG4gICAgICAgIHtcbiAgICAgICAgICBpZDogJ0RlbGV0ZU9sZFZlcnNpb25zJyxcbiAgICAgICAgICBleHBpcmF0aW9uOiBjZGsuRHVyYXRpb24uZGF5cygzNjUpLCAvLyBLZWVwIGZpbGVzIGZvciAxIHllYXJcbiAgICAgICAgICBhYm9ydEluY29tcGxldGVNdWx0aXBhcnRVcGxvYWRBZnRlcjogY2RrLkR1cmF0aW9uLmRheXMoNyksXG4gICAgICAgIH0sXG4gICAgICBdLFxuICAgICAgY29yczogW1xuICAgICAgICB7XG4gICAgICAgICAgYWxsb3dlZE1ldGhvZHM6IFtcbiAgICAgICAgICAgIHMzLkh0dHBNZXRob2RzLkdFVCxcbiAgICAgICAgICAgIHMzLkh0dHBNZXRob2RzLlBPU1QsXG4gICAgICAgICAgICBzMy5IdHRwTWV0aG9kcy5QVVQsXG4gICAgICAgICAgICBzMy5IdHRwTWV0aG9kcy5ERUxFVEUsXG4gICAgICAgICAgICBzMy5IdHRwTWV0aG9kcy5IRUFELFxuICAgICAgICAgIF0sXG4gICAgICAgICAgYWxsb3dlZE9yaWdpbnM6IFsnKiddLCAvLyBTaG91bGQgYmUgcmVzdHJpY3RlZCBpbiBwcm9kdWN0aW9uXG4gICAgICAgICAgYWxsb3dlZEhlYWRlcnM6IFsnKiddLFxuICAgICAgICAgIGV4cG9zZWRIZWFkZXJzOiBbJ0VUYWcnXSxcbiAgICAgICAgICBtYXhBZ2U6IDMwMDAsXG4gICAgICAgIH0sXG4gICAgICBdLFxuICAgICAgcmVtb3ZhbFBvbGljeTogcHJvcHMuZW52aXJvbm1lbnQgPT09ICdwcm9kJyBcbiAgICAgICAgPyBjZGsuUmVtb3ZhbFBvbGljeS5SRVRBSU4gXG4gICAgICAgIDogY2RrLlJlbW92YWxQb2xpY3kuREVTVFJPWSxcbiAgICB9KTtcblxuICAgIC8vIER5bmFtb0RCIFRhYmxlIGZvciBlY2hvIG1ldGFkYXRhXG4gICAgdGhpcy5lY2hvZXNUYWJsZSA9IG5ldyBkeW5hbW9kYi5UYWJsZSh0aGlzLCAnRWNob2VzVGFibGUnLCB7XG4gICAgICB0YWJsZU5hbWU6IGBFY2hvZXNUYWJsZS0ke3Byb3BzLmVudmlyb25tZW50fWAsXG4gICAgICBwYXJ0aXRpb25LZXk6IHtcbiAgICAgICAgbmFtZTogJ3VzZXJJZCcsXG4gICAgICAgIHR5cGU6IGR5bmFtb2RiLkF0dHJpYnV0ZVR5cGUuU1RSSU5HLFxuICAgICAgfSxcbiAgICAgIHNvcnRLZXk6IHtcbiAgICAgICAgbmFtZTogJ2VjaG9JZCcsXG4gICAgICAgIHR5cGU6IGR5bmFtb2RiLkF0dHJpYnV0ZVR5cGUuU1RSSU5HLFxuICAgICAgfSxcbiAgICAgIGJpbGxpbmdNb2RlOiBkeW5hbW9kYi5CaWxsaW5nTW9kZS5QQVlfUEVSX1JFUVVFU1QsXG4gICAgICBlbmNyeXB0aW9uOiBkeW5hbW9kYi5UYWJsZUVuY3J5cHRpb24uQVdTX01BTkFHRUQsXG4gICAgICBwb2ludEluVGltZVJlY292ZXJ5OiBwcm9wcy5lbnZpcm9ubWVudCA9PT0gJ3Byb2QnLFxuICAgICAgcmVtb3ZhbFBvbGljeTogcHJvcHMuZW52aXJvbm1lbnQgPT09ICdwcm9kJyBcbiAgICAgICAgPyBjZGsuUmVtb3ZhbFBvbGljeS5SRVRBSU4gXG4gICAgICAgIDogY2RrLlJlbW92YWxQb2xpY3kuREVTVFJPWSxcbiAgICB9KTtcblxuICAgIC8vIEdsb2JhbCBTZWNvbmRhcnkgSW5kZXggZm9yIGVtb3Rpb24tYmFzZWQgcXVlcmllc1xuICAgIHRoaXMuZWNob2VzVGFibGUuYWRkR2xvYmFsU2Vjb25kYXJ5SW5kZXgoe1xuICAgICAgaW5kZXhOYW1lOiAnZW1vdGlvbi10aW1lc3RhbXAtaW5kZXgnLFxuICAgICAgcGFydGl0aW9uS2V5OiB7XG4gICAgICAgIG5hbWU6ICdlbW90aW9uJyxcbiAgICAgICAgdHlwZTogZHluYW1vZGIuQXR0cmlidXRlVHlwZS5TVFJJTkcsXG4gICAgICB9LFxuICAgICAgc29ydEtleToge1xuICAgICAgICBuYW1lOiAndGltZXN0YW1wJyxcbiAgICAgICAgdHlwZTogZHluYW1vZGIuQXR0cmlidXRlVHlwZS5TVFJJTkcsXG4gICAgICB9LFxuICAgIH0pO1xuXG4gICAgLy8gQ3JlYXRlIElBTSByb2xlIGZvciB1c2VyLXNjb3BlZCBTMyBhY2Nlc3NcbiAgICBjb25zdCB1c2VyUzNBY2Nlc3NSb2xlID0gbmV3IGlhbS5Sb2xlKHRoaXMsICdVc2VyUzNBY2Nlc3NSb2xlJywge1xuICAgICAgYXNzdW1lZEJ5OiBuZXcgaWFtLkZlZGVyYXRlZFByaW5jaXBhbChcbiAgICAgICAgJ2NvZ25pdG8taWRlbnRpdHkuYW1hem9uYXdzLmNvbScsXG4gICAgICAgIHtcbiAgICAgICAgICBTdHJpbmdFcXVhbHM6IHtcbiAgICAgICAgICAgICdjb2duaXRvLWlkZW50aXR5LmFtYXpvbmF3cy5jb206YXVkJzogJyR7Y29nbml0by1pZGVudGl0eS1wb29sLWlkfScsIC8vIFdpbGwgYmUgcmVwbGFjZWRcbiAgICAgICAgICB9LFxuICAgICAgICAgICdGb3JBbnlWYWx1ZTpTdHJpbmdMaWtlJzoge1xuICAgICAgICAgICAgJ2NvZ25pdG8taWRlbnRpdHkuYW1hem9uYXdzLmNvbTphbXInOiAnYXV0aGVudGljYXRlZCcsXG4gICAgICAgICAgfSxcbiAgICAgICAgfSxcbiAgICAgICAgJ3N0czpBc3N1bWVSb2xlV2l0aFdlYklkZW50aXR5J1xuICAgICAgKSxcbiAgICAgIGRlc2NyaXB0aW9uOiAnUm9sZSBmb3IgYXV0aGVudGljYXRlZCB1c2VycyB0byBhY2Nlc3MgUzMgYXVkaW8gZmlsZXMnLFxuICAgIH0pO1xuXG4gICAgLy8gUG9saWN5IGZvciB1c2VyLXNjb3BlZCBTMyBhY2Nlc3NcbiAgICB1c2VyUzNBY2Nlc3NSb2xlLmFkZFRvUG9saWN5KG5ldyBpYW0uUG9saWN5U3RhdGVtZW50KHtcbiAgICAgIGVmZmVjdDogaWFtLkVmZmVjdC5BTExPVyxcbiAgICAgIGFjdGlvbnM6IFtcbiAgICAgICAgJ3MzOkdldE9iamVjdCcsXG4gICAgICAgICdzMzpQdXRPYmplY3QnLFxuICAgICAgICAnczM6RGVsZXRlT2JqZWN0JyxcbiAgICAgIF0sXG4gICAgICByZXNvdXJjZXM6IFtcbiAgICAgICAgdGhpcy5hdWRpb0J1Y2tldC5hcm5Gb3JPYmplY3RzKCcke2NvZ25pdG8taWRlbnRpdHkuYW1hem9uYXdzLmNvbTpzdWJ9LyonKSxcbiAgICAgIF0sXG4gICAgfSkpO1xuXG4gICAgdXNlclMzQWNjZXNzUm9sZS5hZGRUb1BvbGljeShuZXcgaWFtLlBvbGljeVN0YXRlbWVudCh7XG4gICAgICBlZmZlY3Q6IGlhbS5FZmZlY3QuQUxMT1csXG4gICAgICBhY3Rpb25zOiBbXG4gICAgICAgICdzMzpMaXN0QnVja2V0JyxcbiAgICAgIF0sXG4gICAgICByZXNvdXJjZXM6IFt0aGlzLmF1ZGlvQnVja2V0LmJ1Y2tldEFybl0sXG4gICAgICBjb25kaXRpb25zOiB7XG4gICAgICAgIFN0cmluZ0xpa2U6IHtcbiAgICAgICAgICAnczM6cHJlZml4JzogWycke2NvZ25pdG8taWRlbnRpdHkuYW1hem9uYXdzLmNvbTpzdWJ9LyonXSxcbiAgICAgICAgfSxcbiAgICAgIH0sXG4gICAgfSkpO1xuXG4gICAgLy8gT3V0cHV0IGltcG9ydGFudCB2YWx1ZXNcbiAgICBuZXcgY2RrLkNmbk91dHB1dCh0aGlzLCAnQXVkaW9CdWNrZXROYW1lJywge1xuICAgICAgdmFsdWU6IHRoaXMuYXVkaW9CdWNrZXQuYnVja2V0TmFtZSxcbiAgICAgIGRlc2NyaXB0aW9uOiAnUzMgYnVja2V0IGZvciBhdWRpbyBmaWxlcycsXG4gICAgICBleHBvcnROYW1lOiBgJHtwcm9wcy5lbnZpcm9ubWVudH0tQXVkaW9CdWNrZXROYW1lYCxcbiAgICB9KTtcblxuICAgIG5ldyBjZGsuQ2ZuT3V0cHV0KHRoaXMsICdBdWRpb0J1Y2tldEFybicsIHtcbiAgICAgIHZhbHVlOiB0aGlzLmF1ZGlvQnVja2V0LmJ1Y2tldEFybixcbiAgICAgIGRlc2NyaXB0aW9uOiAnUzMgYnVja2V0IEFSTicsXG4gICAgICBleHBvcnROYW1lOiBgJHtwcm9wcy5lbnZpcm9ubWVudH0tQXVkaW9CdWNrZXRBcm5gLFxuICAgIH0pO1xuXG4gICAgbmV3IGNkay5DZm5PdXRwdXQodGhpcywgJ0VjaG9lc1RhYmxlTmFtZScsIHtcbiAgICAgIHZhbHVlOiB0aGlzLmVjaG9lc1RhYmxlLnRhYmxlTmFtZSxcbiAgICAgIGRlc2NyaXB0aW9uOiAnRHluYW1vREIgdGFibGUgZm9yIGVjaG8gbWV0YWRhdGEnLFxuICAgICAgZXhwb3J0TmFtZTogYCR7cHJvcHMuZW52aXJvbm1lbnR9LUVjaG9lc1RhYmxlTmFtZWAsXG4gICAgfSk7XG5cbiAgICBuZXcgY2RrLkNmbk91dHB1dCh0aGlzLCAnRWNob2VzVGFibGVBcm4nLCB7XG4gICAgICB2YWx1ZTogdGhpcy5lY2hvZXNUYWJsZS50YWJsZUFybixcbiAgICAgIGRlc2NyaXB0aW9uOiAnRHluYW1vREIgdGFibGUgQVJOJyxcbiAgICAgIGV4cG9ydE5hbWU6IGAke3Byb3BzLmVudmlyb25tZW50fS1FY2hvZXNUYWJsZUFybmAsXG4gICAgfSk7XG5cbiAgICBuZXcgY2RrLkNmbk91dHB1dCh0aGlzLCAnVXNlclMzQWNjZXNzUm9sZUFybicsIHtcbiAgICAgIHZhbHVlOiB1c2VyUzNBY2Nlc3NSb2xlLnJvbGVBcm4sXG4gICAgICBkZXNjcmlwdGlvbjogJ0lBTSByb2xlIGZvciB1c2VyIFMzIGFjY2VzcycsXG4gICAgICBleHBvcnROYW1lOiBgJHtwcm9wcy5lbnZpcm9ubWVudH0tVXNlclMzQWNjZXNzUm9sZUFybmAsXG4gICAgfSk7XG4gIH1cbn0iXX0=