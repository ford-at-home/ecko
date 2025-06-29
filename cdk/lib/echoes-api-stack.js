"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.EchoesApiStack = void 0;
const cdk = require("aws-cdk-lib");
const lambda = require("aws-cdk-lib/aws-lambda");
const apigateway = require("aws-cdk-lib/aws-apigateway");
const iam = require("aws-cdk-lib/aws-iam");
const logs = require("aws-cdk-lib/aws-logs");
class EchoesApiStack extends cdk.Stack {
    constructor(scope, id, props) {
        super(scope, id, props);
        // Lambda execution role
        const lambdaRole = new iam.Role(this, 'EchoesLambdaRole', {
            assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
            managedPolicies: [
                iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
            ],
        });
        // Permissions for S3
        props.bucket.grantReadWrite(lambdaRole);
        lambdaRole.addToPolicy(new iam.PolicyStatement({
            effect: iam.Effect.ALLOW,
            actions: [
                's3:GeneratePresignedUrl',
                's3:PutObjectAcl',
                's3:GetObjectAcl',
            ],
            resources: [
                props.bucket.bucketArn,
                props.bucket.arnForObjects('*'),
            ],
        }));
        // Permissions for DynamoDB
        props.table.grantReadWriteData(lambdaRole);
        // Permissions for Cognito
        lambdaRole.addToPolicy(new iam.PolicyStatement({
            effect: iam.Effect.ALLOW,
            actions: [
                'cognito-idp:GetUser',
                'cognito-idp:AdminGetUser',
                'cognito-idp:ListUsers',
            ],
            resources: [props.userPool.userPoolArn],
        }));
        // Lambda function for API
        this.lambdaFunction = new lambda.Function(this, 'EchoesApiFunction', {
            functionName: `echoes-api-${props.environment}`,
            runtime: lambda.Runtime.PYTHON_3_11,
            code: lambda.Code.fromAsset('../backend'),
            handler: 'auth_lambda.handler',
            role: lambdaRole,
            environment: {
                ENVIRONMENT: props.environment,
                S3_BUCKET_NAME: props.bucket.bucketName,
                DYNAMODB_TABLE_NAME: props.table.tableName,
                COGNITO_USER_POOL_ID: props.userPool.userPoolId,
                COGNITO_CLIENT_ID: props.userPoolClient.userPoolClientId,
                REGION: this.region,
                LOG_LEVEL: props.environment === 'prod' ? 'INFO' : 'DEBUG',
                JWT_SECRET_KEY: 'your-secret-key-change-in-production',
                CORS_ALLOW_ORIGINS: props.environment === 'prod'
                    ? 'https://echoes.app'
                    : 'https://d2rnrthj5zqye2.cloudfront.net,https://d2s3hf5ze9ab5s.cloudfront.net,http://localhost:3000,http://localhost:8080',
                ALLOWED_ORIGINS: props.environment === 'prod'
                    ? 'https://echoes.app'
                    : 'https://d2rnrthj5zqye2.cloudfront.net,https://d2s3hf5ze9ab5s.cloudfront.net,http://localhost:3000,http://localhost:8080',
                DEBUG: props.environment === 'prod' ? 'false' : 'true',
            },
            timeout: cdk.Duration.seconds(30),
            memorySize: 512,
            // Remove reserved concurrency for dev environment
            // reservedConcurrentExecutions: props.environment === 'prod' ? 100 : 10,
            logRetention: props.environment === 'prod'
                ? logs.RetentionDays.ONE_MONTH
                : logs.RetentionDays.ONE_WEEK,
        });
        // API Gateway
        this.api = new apigateway.RestApi(this, 'EchoesApi', {
            restApiName: `echoes-api-${props.environment}`,
            description: `Echoes API for ${props.environment} environment`,
            defaultCorsPreflightOptions: {
                allowOrigins: props.environment === 'prod'
                    ? ['https://echoes.app'] // Update with actual domain
                    : apigateway.Cors.ALL_ORIGINS,
                allowMethods: apigateway.Cors.ALL_METHODS,
                allowHeaders: [
                    'Content-Type',
                    'X-Amz-Date',
                    'Authorization',
                    'X-Api-Key',
                    'X-Amz-Security-Token',
                ],
            },
            deployOptions: {
                stageName: props.environment,
                metricsEnabled: true,
                loggingLevel: apigateway.MethodLoggingLevel.INFO,
                dataTraceEnabled: props.environment !== 'prod',
                throttlingBurstLimit: 500,
                throttlingRateLimit: 100,
            },
        });
        // Cognito authorizer
        const cognitoAuthorizer = new apigateway.CognitoUserPoolsAuthorizer(this, 'EchoesCognitoAuthorizer', {
            cognitoUserPools: [props.userPool],
            identitySource: 'method.request.header.Authorization',
            authorizerName: 'EchoesAuthorizer',
        });
        // Lambda integration
        const lambdaIntegration = new apigateway.LambdaIntegration(this.lambdaFunction, {
            proxy: true,
            allowTestInvoke: props.environment !== 'prod',
        });
        // API Resources
        // Root endpoint - returns API info (no auth required)
        this.api.root.addMethod('GET', lambdaIntegration);
        // Health check endpoint (no auth required)
        const health = this.api.root.addResource('health');
        health.addMethod('GET', lambdaIntegration);
        // API v1 prefix
        const apiV1 = this.api.root.addResource('api').addResource('v1');
        // Auth endpoints (no Cognito auth required for these)
        const auth = apiV1.addResource('auth');
        auth.addMethod('POST', lambdaIntegration); // Will handle /login, /refresh via proxy
        const authUsers = auth.addResource('users');
        const authUsersCreate = authUsers.addResource('create');
        authUsersCreate.addMethod('POST', lambdaIntegration);
        const authMe = auth.addResource('me');
        authMe.addMethod('GET', lambdaIntegration);
        const authLogin = auth.addResource('login');
        authLogin.addMethod('POST', lambdaIntegration);
        const authRefresh = auth.addResource('refresh');
        authRefresh.addMethod('POST', lambdaIntegration);
        const authLogout = auth.addResource('logout');
        authLogout.addMethod('POST', lambdaIntegration);
        // Echoes endpoints (auth required)
        const echoes = apiV1.addResource('echoes');
        // POST /echoes/init-upload
        const initUpload = echoes.addResource('init-upload');
        initUpload.addMethod('POST', lambdaIntegration); // Temporarily removed auth for testing
        // POST /echoes (create echo)
        echoes.addMethod('POST', lambdaIntegration); // Temporarily removed auth for testing
        // GET /echoes (list echoes)
        echoes.addMethod('GET', lambdaIntegration); // Temporarily removed auth for testing
        // GET /echoes/random
        const random = echoes.addResource('random');
        random.addMethod('GET', lambdaIntegration, {
            authorizer: cognitoAuthorizer,
            authorizationType: apigateway.AuthorizationType.COGNITO,
        });
        // GET /echoes/stats/user
        const stats = echoes.addResource('stats');
        const userStats = stats.addResource('user');
        userStats.addMethod('GET', lambdaIntegration, {
            authorizer: cognitoAuthorizer,
            authorizationType: apigateway.AuthorizationType.COGNITO,
        });
        // POST /echoes/process-upload (alternative upload method)
        const processUpload = echoes.addResource('process-upload');
        processUpload.addMethod('POST', lambdaIntegration, {
            authorizer: cognitoAuthorizer,
            authorizationType: apigateway.AuthorizationType.COGNITO,
        });
        // GET/DELETE /echoes/{echo_id}
        const echoById = echoes.addResource('{echo_id}');
        echoById.addMethod('GET', lambdaIntegration, {
            authorizer: cognitoAuthorizer,
            authorizationType: apigateway.AuthorizationType.COGNITO,
        });
        echoById.addMethod('DELETE', lambdaIntegration, {
            authorizer: cognitoAuthorizer,
            authorizationType: apigateway.AuthorizationType.COGNITO,
        });
        // API usage plan and key (for monitoring)
        const plan = this.api.addUsagePlan('EchoesUsagePlan', {
            name: `echoes-usage-plan-${props.environment}`,
            description: `Usage plan for Echoes ${props.environment}`,
            throttle: {
                rateLimit: 100,
                burstLimit: 200,
            },
            quota: {
                limit: 10000,
                period: apigateway.Period.DAY,
            },
        });
        plan.addApiStage({
            stage: this.api.deploymentStage,
        });
        // Set the apiUrl property
        this.apiUrl = this.api.url;
        // CloudWatch dashboard (optional)
        // Could add custom metrics and monitoring here
        // Output important values
        new cdk.CfnOutput(this, 'ApiGatewayUrl', {
            value: this.api.url,
            description: 'API Gateway URL',
            exportName: `${props.environment}-ApiGatewayUrl`,
        });
        new cdk.CfnOutput(this, 'ApiGatewayId', {
            value: this.api.restApiId,
            description: 'API Gateway ID',
            exportName: `${props.environment}-ApiGatewayId`,
        });
        new cdk.CfnOutput(this, 'LambdaFunctionArn', {
            value: this.lambdaFunction.functionArn,
            description: 'Lambda function ARN',
            exportName: `${props.environment}-LambdaFunctionArn`,
        });
        new cdk.CfnOutput(this, 'LambdaFunctionName', {
            value: this.lambdaFunction.functionName,
            description: 'Lambda function name',
            exportName: `${props.environment}-LambdaFunctionName`,
        });
    }
}
exports.EchoesApiStack = EchoesApiStack;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZWNob2VzLWFwaS1zdGFjay5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImVjaG9lcy1hcGktc3RhY2sudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7O0FBQUEsbUNBQW1DO0FBQ25DLGlEQUFpRDtBQUNqRCx5REFBeUQ7QUFJekQsMkNBQTJDO0FBQzNDLDZDQUE2QztBQVc3QyxNQUFhLGNBQWUsU0FBUSxHQUFHLENBQUMsS0FBSztJQUszQyxZQUFZLEtBQWdCLEVBQUUsRUFBVSxFQUFFLEtBQTBCO1FBQ2xFLEtBQUssQ0FBQyxLQUFLLEVBQUUsRUFBRSxFQUFFLEtBQUssQ0FBQyxDQUFDO1FBRXhCLHdCQUF3QjtRQUN4QixNQUFNLFVBQVUsR0FBRyxJQUFJLEdBQUcsQ0FBQyxJQUFJLENBQUMsSUFBSSxFQUFFLGtCQUFrQixFQUFFO1lBQ3hELFNBQVMsRUFBRSxJQUFJLEdBQUcsQ0FBQyxnQkFBZ0IsQ0FBQyxzQkFBc0IsQ0FBQztZQUMzRCxlQUFlLEVBQUU7Z0JBQ2YsR0FBRyxDQUFDLGFBQWEsQ0FBQyx3QkFBd0IsQ0FBQywwQ0FBMEMsQ0FBQzthQUN2RjtTQUNGLENBQUMsQ0FBQztRQUVILHFCQUFxQjtRQUNyQixLQUFLLENBQUMsTUFBTSxDQUFDLGNBQWMsQ0FBQyxVQUFVLENBQUMsQ0FBQztRQUN4QyxVQUFVLENBQUMsV0FBVyxDQUFDLElBQUksR0FBRyxDQUFDLGVBQWUsQ0FBQztZQUM3QyxNQUFNLEVBQUUsR0FBRyxDQUFDLE1BQU0sQ0FBQyxLQUFLO1lBQ3hCLE9BQU8sRUFBRTtnQkFDUCx5QkFBeUI7Z0JBQ3pCLGlCQUFpQjtnQkFDakIsaUJBQWlCO2FBQ2xCO1lBQ0QsU0FBUyxFQUFFO2dCQUNULEtBQUssQ0FBQyxNQUFNLENBQUMsU0FBUztnQkFDdEIsS0FBSyxDQUFDLE1BQU0sQ0FBQyxhQUFhLENBQUMsR0FBRyxDQUFDO2FBQ2hDO1NBQ0YsQ0FBQyxDQUFDLENBQUM7UUFFSiwyQkFBMkI7UUFDM0IsS0FBSyxDQUFDLEtBQUss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Q0FBQyxJQUFJLEVBQUUsZUFBZSxFQUFFO1lBQ3ZDLEtBQUssRUFBRSxJQUFJLENBQUMsR0FBRyxDQUFDLEdBQUc7WUFDbkIsV0FBVyxFQUFFLGlCQUFpQjtZQUM5QixVQUFVLEVBQUUsR0FBRyxLQUFLLENBQUMsV0FBVyxnQkFBZ0I7U0FDakQsQ0FBQyxDQUFDO1FBRUgsSUFBSSxHQUFHLENBQUMsU0FBUyxDQUFDLElBQUksRUFBRSxjQUFjLEVBQUU7WUFDdEMsS0FBSyxFQUFFLElBQUksQ0FBQyxHQUFHLENBQUMsU0FBUztZQUN6QixXQUFXLEVBQUUsZ0JBQWdCO1lBQzdCLFVBQVUsRUFBRSxHQUFHLEtBQUssQ0FBQyxXQUFXLGVBQWU7U0FDaEQsQ0FBQyxDQUFDO1FBRUgsSUFBSSxHQUFHLENBQUMsU0FBUyxDQUFDLElBQUksRUFBRSxtQkFBbUIsRUFBRTtZQUMzQyxLQUFLLEVBQUUsSUFBSSxDQUFDLGNBQWMsQ0FBQyxXQUFXO1lBQ3RDLFdBQVcsRUFBRSxxQkFBcUI7WUFDbEMsVUFBVSxFQUFFLEdBQUcsS0FBSyxDQUFDLFdBQVcsb0JBQW9CO1NBQ3JELENBQUMsQ0FBQztRQUVILElBQUksR0FBRyxDQUFDLFNBQVMsQ0FBQyxJQUFJLEVBQUUsb0JBQW9CLEVBQUU7WUFDNUMsS0FBSyxFQUFFLElBQUksQ0FBQyxjQUFjLENBQUMsWUFBWTtZQUN2QyxXQUFXLEVBQUUsc0JBQXNCO1lBQ25DLFVBQVUsRUFBRSxHQUFHLEtBQUssQ0FBQyxXQUFXLHFCQUFxQjtTQUN0RCxDQUFDLENBQUM7SUFDTCxDQUFDO0NBQ0Y7QUF4UEQsd0NBd1BDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0ICogYXMgY2RrIGZyb20gJ2F3cy1jZGstbGliJztcbmltcG9ydCAqIGFzIGxhbWJkYSBmcm9tICdhd3MtY2RrLWxpYi9hd3MtbGFtYmRhJztcbmltcG9ydCAqIGFzIGFwaWdhdGV3YXkgZnJvbSAnYXdzLWNkay1saWIvYXdzLWFwaWdhdGV3YXknO1xuaW1wb3J0ICogYXMgczMgZnJvbSAnYXdzLWNkay1saWIvYXdzLXMzJztcbmltcG9ydCAqIGFzIGR5bmFtb2RiIGZyb20gJ2F3cy1jZGstbGliL2F3cy1keW5hbW9kYic7XG5pbXBvcnQgKiBhcyBjb2duaXRvIGZyb20gJ2F3cy1jZGstbGliL2F3cy1jb2duaXRvJztcbmltcG9ydCAqIGFzIGlhbSBmcm9tICdhd3MtY2RrLWxpYi9hd3MtaWFtJztcbmltcG9ydCAqIGFzIGxvZ3MgZnJvbSAnYXdzLWNkay1saWIvYXdzLWxvZ3MnO1xuaW1wb3J0IHsgQ29uc3RydWN0IH0gZnJvbSAnY29uc3RydWN0cyc7XG5cbmV4cG9ydCBpbnRlcmZhY2UgRWNob2VzQXBpU3RhY2tQcm9wcyBleHRlbmRzIGNkay5TdGFja1Byb3BzIHtcbiAgZW52aXJvbm1lbnQ6IHN0cmluZztcbiAgYnVja2V0OiBzMy5CdWNrZXQ7XG4gIHRhYmxlOiBkeW5hbW9kYi5UYWJsZTtcbiAgdXNlclBvb2w6IGNvZ25pdG8uVXNlclBvb2w7XG4gIHVzZXJQb29sQ2xpZW50OiBjb2duaXRvLlVzZXJQb29sQ2xpZW50O1xufVxuXG5leHBvcnQgY2xhc3MgRWNob2VzQXBpU3RhY2sgZXh0ZW5kcyBjZGsuU3RhY2sge1xuICBwdWJsaWMgcmVhZG9ubHkgYXBpOiBhcGlnYXRld2F5LlJlc3RBcGk7XG4gIHB1YmxpYyByZWFkb25seSBsYW1iZGFGdW5jdGlvbjogbGFtYmRhLkZ1bmN0aW9uO1xuICBwdWJsaWMgcmVhZG9ubHkgYXBpVXJsOiBzdHJpbmc7XG5cbiAgY29uc3RydWN0b3Ioc2NvcGU6IENvbnN0cnVjdCwgaWQ6IHN0cmluZywgcHJvcHM6IEVjaG9lc0FwaVN0YWNrUHJvcHMpIHtcbiAgICBzdXBlcihzY29wZSwgaWQsIHByb3BzKTtcblxuICAgIC8vIExhbWJkYSBleGVjdXRpb24gcm9sZVxuICAgIGNvbnN0IGxhbWJkYVJvbGUgPSBuZXcgaWFtLlJvbGUodGhpcywgJ0VjaG9lc0xhbWJkYVJvbGUnLCB7XG4gICAgICBhc3N1bWVkQnk6IG5ldyBpYW0uU2VydmljZVByaW5jaXBhbCgnbGFtYmRhLmFtYXpvbmF3cy5jb20nKSxcbiAgICAgIG1hbmFnZWRQb2xpY2llczogW1xuICAgICAgICBpYW0uTWFuYWdlZFBvbGljeS5mcm9tQXdzTWFuYWdlZFBvbGljeU5hbWUoJ3NlcnZpY2Utcm9sZS9BV1NMYW1iZGFCYXNpY0V4ZWN1dGlvblJvbGUnKSxcbiAgICAgIF0sXG4gICAgfSk7XG5cbiAgICAvLyBQZXJtaXNzaW9ucyBmb3IgUzNcbiAgICBwcm9wcy5idWNrZXQuZ3JhbnRSZWFkV3JpdGUobGFtYmRhUm9sZSk7XG4gICAgbGFtYmRhUm9sZS5hZGRUb1BvbGljeShuZXcgaWFtLlBvbGljeVN0YXRlbWVudCh7XG4gICAgICBlZmZlY3Q6IGlhbS5FZmZlY3QuQUxMT1csXG4gICAgICBhY3Rpb25zOiBbXG4gICAgICAgICdzMzpHZW5lcmF0ZVByZXNpZ25lZFVybCcsXG4gICAgICAgICdzMzpQdXRPYmplY3RBY2wnLFxuICAgICAgICAnczM6R2V0T2JqZWN0QWNsJyxcbiAgICAgIF0sXG4gICAgICByZXNvdXJjZXM6IFtcbiAgICAgICAgcHJvcHMuYnVja2V0LmJ1Y2tldEFybixcbiAgICAgICAgcHJvcHMuYnVja2V0LmFybkZvck9iamVjdHMoJyonKSxcbiAgICAgIF0sXG4gICAgfSkpO1xuXG4gICAgLy8gUGVybWlzc2lvbnMgZm9yIER5bmFtb0RCXG4gICAgcHJvcHMudGFibGUuZ3JhbnRSZWFkV3JpdGVEYXRhKGxhbWJkYVJvbGUpO1xuXG4gICAgLy8gUGVybWlzc2lvbnMgZm9yIENvZ25pdG9cbiAgICBsYW1iZGFSb2xlLmFkZFRvUG9saWN5KG5ldyBpYW0uUG9saWN5U3RhdGVtZW50KHtcbiAgICAgIGVmZmVjdDogaWFtLkVmZmVjdC5BTExPVyxcbiAgICAgIGFjdGlvbnM6IFtcbiAgICAgICAgJ2NvZ25pdG8taWRwOkdldFVzZXInLFxuICAgICAgICAnY29nbml0by1pZHA6QWRtaW5HZXRVc2VyJyxcbiAgICAgICAgJ2NvZ25pdG8taWRwOkxpc3RVc2VycycsXG4gICAgICBdLFxuICAgICAgcmVzb3VyY2VzOiBbcHJvcHMudXNlclBvb2wudXNlclBvb2xBcm5dLFxuICAgIH0pKTtcblxuICAgIC8vIExhbWJkYSBmdW5jdGlvbiBmb3IgQVBJXG4gICAgdGhpcy5sYW1iZGFGdW5jdGlvbiA9IG5ldyBsYW1iZGEuRnVuY3Rpb24odGhpcywgJ0VjaG9lc0FwaUZ1bmN0aW9uJywge1xuICAgICAgZnVuY3Rpb25OYW1lOiBgZWNob2VzLWFwaS0ke3Byb3BzLmVudmlyb25tZW50fWAsXG4gICAgICBydW50aW1lOiBsYW1iZGEuUnVudGltZS5QWVRIT05fM18xMSxcbiAgICAgIGNvZGU6IGxhbWJkYS5Db2RlLmZyb21Bc3NldCgnLi4vYmFja2VuZCcpLFxuICAgICAgaGFuZGxlcjogJ2F1dGhfbGFtYmRhLmhhbmRsZXInLFxuICAgICAgcm9sZTogbGFtYmRhUm9sZSxcbiAgICAgIGVudmlyb25tZW50OiB7XG4gICAgICAgIEVOVklST05NRU5UOiBwcm9wcy5lbnZpcm9ubWVudCxcbiAgICAgICAgUzNfQlVDS0VUX05BTUU6IHByb3BzLmJ1Y2tldC5idWNrZXROYW1lLFxuICAgICAgICBEWU5BTU9EQl9UQUJMRV9OQU1FOiBwcm9wcy50YWJsZS50YWJsZU5hbWUsXG4gICAgICAgIENPR05JVE9fVVNFUl9QT09MX0lEOiBwcm9wcy51c2VyUG9vbC51c2VyUG9vbElkLFxuICAgICAgICBDT0dOSVRPX0NMSUVOVF9JRDogcHJvcHMudXNlclBvb2xDbGllbnQudXNlclBvb2xDbGllbnRJZCxcbiAgICAgICAgUkVHSU9OOiB0aGlzLnJlZ2lvbixcbiAgICAgICAgTE9HX0xFVkVMOiBwcm9wcy5lbnZpcm9ubWVudCA9PT0gJ3Byb2QnID8gJ0lORk8nIDogJ0RFQlVHJyxcbiAgICAgICAgSldUX1NFQ1JFVF9LRVk6ICd5b3VyLXNlY3JldC1rZXktY2hhbmdlLWluLXByb2R1Y3Rpb24nLCAvLyBUT0RPOiBVc2UgU2VjcmV0cyBNYW5hZ2VyXG4gICAgICAgIENPUlNfQUxMT1dfT1JJR0lOUzogcHJvcHMuZW52aXJvbm1lbnQgPT09ICdwcm9kJyBcbiAgICAgICAgICA/ICdodHRwczovL2VjaG9lcy5hcHAnIFxuICAgICAgICAgIDogJ2h0dHBzOi8vZDJybnJ0aGo1enF5ZTIuY2xvdWRmcm9udC5uZXQsaHR0cHM6Ly9kMnMzaGY1emU5YWI1cy5jbG91ZGZyb250Lm5ldCxodHRwOi8vbG9jYWxob3N0OjMwMDAsaHR0cDovL2xvY2FsaG9zdDo4MDgwJyxcbiAgICAgICAgQUxMT1dFRF9PUklHSU5TOiBwcm9wcy5lbnZpcm9ubWVudCA9PT0gJ3Byb2QnIFxuICAgICAgICAgID8gJ2h0dHBzOi8vZWNob2VzLmFwcCcgXG4gICAgICAgICAgOiAnaHR0cHM6Ly9kMnJucnRoajV6cXllMi5jbG91ZGZyb250Lm5ldCxodHRwczovL2QyczNoZjV6ZTlhYjVzLmNsb3VkZnJvbnQubmV0LGh0dHA6Ly9sb2NhbGhvc3Q6MzAwMCxodHRwOi8vbG9jYWxob3N0OjgwODAnLFxuICAgICAgICBERUJVRzogcHJvcHMuZW52aXJvbm1lbnQgPT09ICdwcm9kJyA/ICdmYWxzZScgOiAndHJ1ZScsXG4gICAgICB9LFxuICAgICAgdGltZW91dDogY2RrLkR1cmF0aW9uLnNlY29uZHMoMzApLFxuICAgICAgbWVtb3J5U2l6ZTogNTEyLFxuICAgICAgLy8gUmVtb3ZlIHJlc2VydmVkIGNvbmN1cnJlbmN5IGZvciBkZXYgZW52aXJvbm1lbnRcbiAgICAgIC8vIHJlc2VydmVkQ29uY3VycmVudEV4ZWN1dGlvbnM6IHByb3BzLmVudmlyb25tZW50ID09PSAncHJvZCcgPyAxMDAgOiAxMCxcbiAgICAgIGxvZ1JldGVudGlvbjogcHJvcHMuZW52aXJvbm1lbnQgPT09ICdwcm9kJyBcbiAgICAgICAgPyBsb2dzLlJldGVudGlvbkRheXMuT05FX01PTlRIIFxuICAgICAgICA6IGxvZ3MuUmV0ZW50aW9uRGF5cy5PTkVfV0VFSyxcbiAgICB9KTtcblxuICAgIC8vIEFQSSBHYXRld2F5XG4gICAgdGhpcy5hcGkgPSBuZXcgYXBpZ2F0ZXdheS5SZXN0QXBpKHRoaXMsICdFY2hvZXNBcGknLCB7XG4gICAgICByZXN0QXBpTmFtZTogYGVjaG9lcy1hcGktJHtwcm9wcy5lbnZpcm9ubWVudH1gLFxuICAgICAgZGVzY3JpcHRpb246IGBFY2hvZXMgQVBJIGZvciAke3Byb3BzLmVudmlyb25tZW50fSBlbnZpcm9ubWVudGAsXG4gICAgICBkZWZhdWx0Q29yc1ByZWZsaWdodE9wdGlvbnM6IHtcbiAgICAgICAgYWxsb3dPcmlnaW5zOiBwcm9wcy5lbnZpcm9ubWVudCA9PT0gJ3Byb2QnIFxuICAgICAgICAgID8gWydodHRwczovL2VjaG9lcy5hcHAnXSAvLyBVcGRhdGUgd2l0aCBhY3R1YWwgZG9tYWluXG4gICAgICAgICAgOiBhcGlnYXRld2F5LkNvcnMuQUxMX09SSUdJTlMsXG4gICAgICAgIGFsbG93TWV0aG9kczogYXBpZ2F0ZXdheS5Db3JzLkFMTF9NRVRIT0RTLFxuICAgICAgICBhbGxvd0hlYWRlcnM6IFtcbiAgICAgICAgICAnQ29udGVudC1UeXBlJyxcbiAgICAgICAgICAnWC1BbXotRGF0ZScsXG4gICAgICAgICAgJ0F1dGhvcml6YXRpb24nLFxuICAgICAgICAgICdYLUFwaS1LZXknLFxuICAgICAgICAgICdYLUFtei1TZWN1cml0eS1Ub2tlbicsXG4gICAgICAgIF0sXG4gICAgICB9LFxuICAgICAgZGVwbG95T3B0aW9uczoge1xuICAgICAgICBzdGFnZU5hbWU6IHByb3BzLmVudmlyb25tZW50LFxuICAgICAgICBtZXRyaWNzRW5hYmxlZDogdHJ1ZSxcbiAgICAgICAgbG9nZ2luZ0xldmVsOiBhcGlnYXRld2F5Lk1ldGhvZExvZ2dpbmdMZXZlbC5JTkZPLFxuICAgICAgICBkYXRhVHJhY2VFbmFibGVkOiBwcm9wcy5lbnZpcm9ubWVudCAhPT0gJ3Byb2QnLFxuICAgICAgICB0aHJvdHRsaW5nQnVyc3RMaW1pdDogNTAwLFxuICAgICAgICB0aHJvdHRsaW5nUmF0ZUxpbWl0OiAxMDAsXG4gICAgICB9LFxuICAgIH0pO1xuXG4gICAgLy8gQ29nbml0byBhdXRob3JpemVyXG4gICAgY29uc3QgY29nbml0b0F1dGhvcml6ZXIgPSBuZXcgYXBpZ2F0ZXdheS5Db2duaXRvVXNlclBvb2xzQXV0aG9yaXplcihcbiAgICAgIHRoaXMsXG4gICAgICAnRWNob2VzQ29nbml0b0F1dGhvcml6ZXInLFxuICAgICAge1xuICAgICAgICBjb2duaXRvVXNlclBvb2xzOiBbcHJvcHMudXNlclBvb2xdLFxuICAgICAgICBpZGVudGl0eVNvdXJjZTogJ21ldGhvZC5yZXF1ZXN0LmhlYWRlci5BdXRob3JpemF0aW9uJyxcbiAgICAgICAgYXV0aG9yaXplck5hbWU6ICdFY2hvZXNBdXRob3JpemVyJyxcbiAgICAgIH1cbiAgICApO1xuXG4gICAgLy8gTGFtYmRhIGludGVncmF0aW9uXG4gICAgY29uc3QgbGFtYmRhSW50ZWdyYXRpb24gPSBuZXcgYXBpZ2F0ZXdheS5MYW1iZGFJbnRlZ3JhdGlvbih0aGlzLmxhbWJkYUZ1bmN0aW9uLCB7XG4gICAgICBwcm94eTogdHJ1ZSxcbiAgICAgIGFsbG93VGVzdEludm9rZTogcHJvcHMuZW52aXJvbm1lbnQgIT09ICdwcm9kJyxcbiAgICB9KTtcblxuICAgIC8vIEFQSSBSZXNvdXJjZXNcbiAgICAvLyBSb290IGVuZHBvaW50IC0gcmV0dXJucyBBUEkgaW5mbyAobm8gYXV0aCByZXF1aXJlZClcbiAgICB0aGlzLmFwaS5yb290LmFkZE1ldGhvZCgnR0VUJywgbGFtYmRhSW50ZWdyYXRpb24pO1xuICAgIFxuICAgIC8vIEhlYWx0aCBjaGVjayBlbmRwb2ludCAobm8gYXV0aCByZXF1aXJlZClcbiAgICBjb25zdCBoZWFsdGggPSB0aGlzLmFwaS5yb290LmFkZFJlc291cmNlKCdoZWFsdGgnKTtcbiAgICBoZWFsdGguYWRkTWV0aG9kKCdHRVQnLCBsYW1iZGFJbnRlZ3JhdGlvbik7XG5cbiAgICAvLyBBUEkgdjEgcHJlZml4XG4gICAgY29uc3QgYXBpVjEgPSB0aGlzLmFwaS5yb290LmFkZFJlc291cmNlKCdhcGknKS5hZGRSZXNvdXJjZSgndjEnKTtcblxuICAgIC8vIEF1dGggZW5kcG9pbnRzIChubyBDb2duaXRvIGF1dGggcmVxdWlyZWQgZm9yIHRoZXNlKVxuICAgIGNvbnN0IGF1dGggPSBhcGlWMS5hZGRSZXNvdXJjZSgnYXV0aCcpO1xuICAgIGF1dGguYWRkTWV0aG9kKCdQT1NUJywgbGFtYmRhSW50ZWdyYXRpb24pOyAvLyBXaWxsIGhhbmRsZSAvbG9naW4sIC9yZWZyZXNoIHZpYSBwcm94eVxuICAgIFxuICAgIGNvbnN0IGF1dGhVc2VycyA9IGF1dGguYWRkUmVzb3VyY2UoJ3VzZXJzJyk7XG4gICAgY29uc3QgYXV0aFVzZXJzQ3JlYXRlID0gYXV0aFVzZXJzLmFkZFJlc291cmNlKCdjcmVhdGUnKTtcbiAgICBhdXRoVXNlcnNDcmVhdGUuYWRkTWV0aG9kKCdQT1NUJywgbGFtYmRhSW50ZWdyYXRpb24pO1xuICAgIFxuICAgIGNvbnN0IGF1dGhNZSA9IGF1dGguYWRkUmVzb3VyY2UoJ21lJyk7XG4gICAgYXV0aE1lLmFkZE1ldGhvZCgnR0VUJywgbGFtYmRhSW50ZWdyYXRpb24pO1xuICAgIFxuICAgIGNvbnN0IGF1dGhMb2dpbiA9IGF1dGguYWRkUmVzb3VyY2UoJ2xvZ2luJyk7XG4gICAgYXV0aExvZ2luLmFkZE1ldGhvZCgnUE9TVCcsIGxhbWJkYUludGVncmF0aW9uKTtcbiAgICBcbiAgICBjb25zdCBhdXRoUmVmcmVzaCA9IGF1dGguYWRkUmVzb3VyY2UoJ3JlZnJlc2gnKTtcbiAgICBhdXRoUmVmcmVzaC5hZGRNZXRob2QoJ1BPU1QnLCBsYW1iZGFJbnRlZ3JhdGlvbik7XG4gICAgXG4gICAgY29uc3QgYXV0aExvZ291dCA9IGF1dGguYWRkUmVzb3VyY2UoJ2xvZ291dCcpO1xuICAgIGF1dGhMb2dvdXQuYWRkTWV0aG9kKCdQT1NUJywgbGFtYmRhSW50ZWdyYXRpb24pO1xuXG4gICAgLy8gRWNob2VzIGVuZHBvaW50cyAoYXV0aCByZXF1aXJlZClcbiAgICBjb25zdCBlY2hvZXMgPSBhcGlWMS5hZGRSZXNvdXJjZSgnZWNob2VzJyk7XG4gICAgXG4gICAgLy8gUE9TVCAvZWNob2VzL2luaXQtdXBsb2FkXG4gICAgY29uc3QgaW5pdFVwbG9hZCA9IGVjaG9lcy5hZGRSZXNvdXJjZSgnaW5pdC11cGxvYWQnKTtcbiAgICBpbml0VXBsb2FkLmFkZE1ldGhvZCgnUE9TVCcsIGxhbWJkYUludGVncmF0aW9uKTsgLy8gVGVtcG9yYXJpbHkgcmVtb3ZlZCBhdXRoIGZvciB0ZXN0aW5nXG5cbiAgICAvLyBQT1NUIC9lY2hvZXMgKGNyZWF0ZSBlY2hvKVxuICAgIGVjaG9lcy5hZGRNZXRob2QoJ1BPU1QnLCBsYW1iZGFJbnRlZ3JhdGlvbik7IC8vIFRlbXBvcmFyaWx5IHJlbW92ZWQgYXV0aCBmb3IgdGVzdGluZ1xuXG4gICAgLy8gR0VUIC9lY2hvZXMgKGxpc3QgZWNob2VzKVxuICAgIGVjaG9lcy5hZGRNZXRob2QoJ0dFVCcsIGxhbWJkYUludGVncmF0aW9uKTsgLy8gVGVtcG9yYXJpbHkgcmVtb3ZlZCBhdXRoIGZvciB0ZXN0aW5nXG5cbiAgICAvLyBHRVQgL2VjaG9lcy9yYW5kb21cbiAgICBjb25zdCByYW5kb20gPSBlY2hvZXMuYWRkUmVzb3VyY2UoJ3JhbmRvbScpO1xuICAgIHJhbmRvbS5hZGRNZXRob2QoJ0dFVCcsIGxhbWJkYUludGVncmF0aW9uLCB7XG4gICAgICBhdXRob3JpemVyOiBjb2duaXRvQXV0aG9yaXplcixcbiAgICAgIGF1dGhvcml6YXRpb25UeXBlOiBhcGlnYXRld2F5LkF1dGhvcml6YXRpb25UeXBlLkNPR05JVE8sXG4gICAgfSk7XG5cbiAgICAvLyBHRVQgL2VjaG9lcy9zdGF0cy91c2VyXG4gICAgY29uc3Qgc3RhdHMgPSBlY2hvZXMuYWRkUmVzb3VyY2UoJ3N0YXRzJyk7XG4gICAgY29uc3QgdXNlclN0YXRzID0gc3RhdHMuYWRkUmVzb3VyY2UoJ3VzZXInKTtcbiAgICB1c2VyU3RhdHMuYWRkTWV0aG9kKCdHRVQnLCBsYW1iZGFJbnRlZ3JhdGlvbiwge1xuICAgICAgYXV0aG9yaXplcjogY29nbml0b0F1dGhvcml6ZXIsXG4gICAgICBhdXRob3JpemF0aW9uVHlwZTogYXBpZ2F0ZXdheS5BdXRob3JpemF0aW9uVHlwZS5DT0dOSVRPLFxuICAgIH0pO1xuXG4gICAgLy8gUE9TVCAvZWNob2VzL3Byb2Nlc3MtdXBsb2FkIChhbHRlcm5hdGl2ZSB1cGxvYWQgbWV0aG9kKVxuICAgIGNvbnN0IHByb2Nlc3NVcGxvYWQgPSBlY2hvZXMuYWRkUmVzb3VyY2UoJ3Byb2Nlc3MtdXBsb2FkJyk7XG4gICAgcHJvY2Vzc1VwbG9hZC5hZGRNZXRob2QoJ1BPU1QnLCBsYW1iZGFJbnRlZ3JhdGlvbiwge1xuICAgICAgYXV0aG9yaXplcjogY29nbml0b0F1dGhvcml6ZXIsXG4gICAgICBhdXRob3JpemF0aW9uVHlwZTogYXBpZ2F0ZXdheS5BdXRob3JpemF0aW9uVHlwZS5DT0dOSVRPLFxuICAgIH0pO1xuXG4gICAgLy8gR0VUL0RFTEVURSAvZWNob2VzL3tlY2hvX2lkfVxuICAgIGNvbnN0IGVjaG9CeUlkID0gZWNob2VzLmFkZFJlc291cmNlKCd7ZWNob19pZH0nKTtcbiAgICBlY2hvQnlJZC5hZGRNZXRob2QoJ0dFVCcsIGxhbWJkYUludGVncmF0aW9uLCB7XG4gICAgICBhdXRob3JpemVyOiBjb2duaXRvQXV0aG9yaXplcixcbiAgICAgIGF1dGhvcml6YXRpb25UeXBlOiBhcGlnYXRld2F5LkF1dGhvcml6YXRpb25UeXBlLkNPR05JVE8sXG4gICAgfSk7XG4gICAgZWNob0J5SWQuYWRkTWV0aG9kKCdERUxFVEUnLCBsYW1iZGFJbnRlZ3JhdGlvbiwge1xuICAgICAgYXV0aG9yaXplcjogY29nbml0b0F1dGhvcml6ZXIsXG4gICAgICBhdXRob3JpemF0aW9uVHlwZTogYXBpZ2F0ZXdheS5BdXRob3JpemF0aW9uVHlwZS5DT0dOSVRPLFxuICAgIH0pO1xuXG4gICAgLy8gQVBJIHVzYWdlIHBsYW4gYW5kIGtleSAoZm9yIG1vbml0b3JpbmcpXG4gICAgY29uc3QgcGxhbiA9IHRoaXMuYXBpLmFkZFVzYWdlUGxhbignRWNob2VzVXNhZ2VQbGFuJywge1xuICAgICAgbmFtZTogYGVjaG9lcy11c2FnZS1wbGFuLSR7cHJvcHMuZW52aXJvbm1lbnR9YCxcbiAgICAgIGRlc2NyaXB0aW9uOiBgVXNhZ2UgcGxhbiBmb3IgRWNob2VzICR7cHJvcHMuZW52aXJvbm1lbnR9YCxcbiAgICAgIHRocm90dGxlOiB7XG4gICAgICAgIHJhdGVMaW1pdDogMTAwLFxuICAgICAgICBidXJzdExpbWl0OiAyMDAsXG4gICAgICB9LFxuICAgICAgcXVvdGE6IHtcbiAgICAgICAgbGltaXQ6IDEwMDAwLFxuICAgICAgICBwZXJpb2Q6IGFwaWdhdGV3YXkuUGVyaW9kLkRBWSxcbiAgICAgIH0sXG4gICAgfSk7XG5cbiAgICBwbGFuLmFkZEFwaVN0YWdlKHtcbiAgICAgIHN0YWdlOiB0aGlzLmFwaS5kZXBsb3ltZW50U3RhZ2UsXG4gICAgfSk7XG5cbiAgICAvLyBTZXQgdGhlIGFwaVVybCBwcm9wZXJ0eVxuICAgIHRoaXMuYXBpVXJsID0gdGhpcy5hcGkudXJsO1xuXG4gICAgLy8gQ2xvdWRXYXRjaCBkYXNoYm9hcmQgKG9wdGlvbmFsKVxuICAgIC8vIENvdWxkIGFkZCBjdXN0b20gbWV0cmljcyBhbmQgbW9uaXRvcmluZyBoZXJlXG5cbiAgICAvLyBPdXRwdXQgaW1wb3J0YW50IHZhbHVlc1xuICAgIG5ldyBjZGsuQ2ZuT3V0cHV0KHRoaXMsICdBcGlHYXRld2F5VXJsJywge1xuICAgICAgdmFsdWU6IHRoaXMuYXBpLnVybCxcbiAgICAgIGRlc2NyaXB0aW9uOiAnQVBJIEdhdGV3YXkgVVJMJyxcbiAgICAgIGV4cG9ydE5hbWU6IGAke3Byb3BzLmVudmlyb25tZW50fS1BcGlHYXRld2F5VXJsYCxcbiAgICB9KTtcblxuICAgIG5ldyBjZGsuQ2ZuT3V0cHV0KHRoaXMsICdBcGlHYXRld2F5SWQnLCB7XG4gICAgICB2YWx1ZTogdGhpcy5hcGkucmVzdEFwaUlkLFxuICAgICAgZGVzY3JpcHRpb246ICdBUEkgR2F0ZXdheSBJRCcsXG4gICAgICBleHBvcnROYW1lOiBgJHtwcm9wcy5lbnZpcm9ubWVudH0tQXBpR2F0ZXdheUlkYCxcbiAgICB9KTtcblxuICAgIG5ldyBjZGsuQ2ZuT3V0cHV0KHRoaXMsICdMYW1iZGFGdW5jdGlvbkFybicsIHtcbiAgICAgIHZhbHVlOiB0aGlzLmxhbWJkYUZ1bmN0aW9uLmZ1bmN0aW9uQXJuLFxuICAgICAgZGVzY3JpcHRpb246ICdMYW1iZGEgZnVuY3Rpb24gQVJOJyxcbiAgICAgIGV4cG9ydE5hbWU6IGAke3Byb3BzLmVudmlyb25tZW50fS1MYW1iZGFGdW5jdGlvbkFybmAsXG4gICAgfSk7XG5cbiAgICBuZXcgY2RrLkNmbk91dHB1dCh0aGlzLCAnTGFtYmRhRnVuY3Rpb25OYW1lJywge1xuICAgICAgdmFsdWU6IHRoaXMubGFtYmRhRnVuY3Rpb24uZnVuY3Rpb25OYW1lLFxuICAgICAgZGVzY3JpcHRpb246ICdMYW1iZGEgZnVuY3Rpb24gbmFtZScsXG4gICAgICBleHBvcnROYW1lOiBgJHtwcm9wcy5lbnZpcm9ubWVudH0tTGFtYmRhRnVuY3Rpb25OYW1lYCxcbiAgICB9KTtcbiAgfVxufSJdfQ==