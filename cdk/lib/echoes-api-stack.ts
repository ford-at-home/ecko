import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';

export interface EchoesApiStackProps extends cdk.StackProps {
  environment: string;
  bucket: s3.Bucket;
  table: dynamodb.Table;
  userPool: cognito.UserPool;
  userPoolClient: cognito.UserPoolClient;
}

export class EchoesApiStack extends cdk.Stack {
  public readonly api: apigateway.RestApi;
  public readonly lambdaFunction: lambda.Function;

  constructor(scope: Construct, id: string, props: EchoesApiStackProps) {
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
      handler: 'simple_lambda.handler',
      role: lambdaRole,
      environment: {
        ENVIRONMENT: props.environment,
        S3_BUCKET_NAME: props.bucket.bucketName,
        DYNAMODB_TABLE_NAME: props.table.tableName,
        COGNITO_USER_POOL_ID: props.userPool.userPoolId,
        COGNITO_CLIENT_ID: props.userPoolClient.userPoolClientId,
        REGION: this.region,
        LOG_LEVEL: props.environment === 'prod' ? 'INFO' : 'DEBUG',
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
    const cognitoAuthorizer = new apigateway.CognitoUserPoolsAuthorizer(
      this,
      'EchoesCognitoAuthorizer',
      {
        cognitoUserPools: [props.userPool],
        identitySource: 'method.request.header.Authorization',
        authorizerName: 'EchoesAuthorizer',
      }
    );

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

    // Echoes endpoints (auth required)
    const echoes = this.api.root.addResource('echoes');
    
    // POST /echoes/init-upload
    const initUpload = echoes.addResource('init-upload');
    initUpload.addMethod('POST', lambdaIntegration, {
      authorizer: cognitoAuthorizer,
      authorizationType: apigateway.AuthorizationType.COGNITO,
    });

    // POST /echoes (create echo)
    echoes.addMethod('POST', lambdaIntegration, {
      authorizer: cognitoAuthorizer,
      authorizationType: apigateway.AuthorizationType.COGNITO,
    });

    // GET /echoes (list echoes)
    echoes.addMethod('GET', lambdaIntegration, {
      authorizer: cognitoAuthorizer,
      authorizationType: apigateway.AuthorizationType.COGNITO,
    });

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