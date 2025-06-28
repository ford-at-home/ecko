import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';

interface EchoesApiStackProps extends cdk.StackProps {
  environment: string;
  userPool: cognito.UserPool;
  identityPool: cognito.CfnIdentityPool;
  echoesTable: dynamodb.Table;
  audiosBucket: s3.Bucket;
}

export class EchoesApiStack extends cdk.Stack {
  public readonly api: apigateway.RestApi;
  public readonly initUploadFunction: lambda.Function;
  public readonly saveEchoFunction: lambda.Function;
  public readonly getEchoesFunction: lambda.Function;
  public readonly getRandomEchoFunction: lambda.Function;

  constructor(scope: Construct, id: string, props: EchoesApiStackProps) {
    super(scope, id, props);

    const { environment, userPool, identityPool, echoesTable, audiosBucket } = props;

    // Common Lambda environment variables
    const lambdaEnvironment = {
      ECHOES_TABLE_NAME: echoesTable.tableName,
      AUDIOS_BUCKET_NAME: audiosBucket.bucketName,
      USER_POOL_ID: userPool.userPoolId,
      IDENTITY_POOL_ID: identityPool.ref,
      ENVIRONMENT: environment,
    };

    // Common Lambda execution role
    const lambdaRole = new iam.Role(this, 'LambdaExecutionRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
      inlinePolicies: {
        EchoesLambdaPolicy: new iam.PolicyDocument({
          statements: [
            // DynamoDB permissions
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'dynamodb:GetItem',
                'dynamodb:PutItem',
                'dynamodb:UpdateItem',
                'dynamodb:DeleteItem',
                'dynamodb:Query',
                'dynamodb:Scan',
              ],
              resources: [
                echoesTable.tableArn,
                `${echoesTable.tableArn}/index/*`,
              ],
            }),
            // S3 permissions
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                's3:GetObject',
                's3:PutObject',
                's3:DeleteObject',
                's3:GetObjectVersion',
              ],
              resources: [`${audiosBucket.bucketArn}/*`],
            }),
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: ['s3:ListBucket'],
              resources: [audiosBucket.bucketArn],
            }),
            // CloudWatch Logs
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'logs:CreateLogGroup',
                'logs:CreateLogStream',
                'logs:PutLogEvents',
              ],
              resources: ['*'],
            }),
          ],
        }),
      },
    });

    // Lambda Functions
    this.initUploadFunction = new lambda.Function(this, 'InitUploadFunction', {
      functionName: `echoes-init-upload-${environment}`,
      runtime: lambda.Runtime.NODEJS_18_X,
      handler: 'index.handler',
      code: lambda.Code.fromAsset('lambda/init-upload'),
      environment: lambdaEnvironment,
      role: lambdaRole,
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
      logRetention: logs.RetentionDays.ONE_MONTH,
      deadLetterQueue: new cdk.aws_sqs.Queue(this, 'InitUploadDLQ', {
        queueName: `echoes-init-upload-dlq-${environment}`,
        retentionPeriod: cdk.Duration.days(14),
      }),
    });

    this.saveEchoFunction = new lambda.Function(this, 'SaveEchoFunction', {
      functionName: `echoes-save-echo-${environment}`,
      runtime: lambda.Runtime.NODEJS_18_X,
      handler: 'index.handler',
      code: lambda.Code.fromAsset('lambda/save-echo'),
      environment: lambdaEnvironment,
      role: lambdaRole,
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
      logRetention: logs.RetentionDays.ONE_MONTH,
      deadLetterQueue: new cdk.aws_sqs.Queue(this, 'SaveEchoDLQ', {
        queueName: `echoes-save-echo-dlq-${environment}`,
        retentionPeriod: cdk.Duration.days(14),
      }),
    });

    this.getEchoesFunction = new lambda.Function(this, 'GetEchoesFunction', {
      functionName: `echoes-get-echoes-${environment}`,
      runtime: lambda.Runtime.NODEJS_18_X,
      handler: 'index.handler',
      code: lambda.Code.fromAsset('lambda/get-echoes'),
      environment: lambdaEnvironment,
      role: lambdaRole,
      timeout: cdk.Duration.seconds(30),
      memorySize: 512, // Higher memory for query operations
      logRetention: logs.RetentionDays.ONE_MONTH,
    });

    this.getRandomEchoFunction = new lambda.Function(this, 'GetRandomEchoFunction', {
      functionName: `echoes-get-random-echo-${environment}`,
      runtime: lambda.Runtime.NODEJS_18_X,
      handler: 'index.handler',
      code: lambda.Code.fromAsset('lambda/get-random-echo'),
      environment: lambdaEnvironment,
      role: lambdaRole,
      timeout: cdk.Duration.seconds(30),
      memorySize: 512,
      logRetention: logs.RetentionDays.ONE_MONTH,
    });

    // API Gateway
    this.api = new apigateway.RestApi(this, 'EchoesApi', {
      restApiName: `echoes-api-${environment}`,
      description: 'API for Echoes audio time machine',
      deployOptions: {
        stageName: environment,
        throttlingRateLimit: 100,
        throttlingBurstLimit: 200,
        loggingLevel: apigateway.MethodLoggingLevel.INFO,
        accessLogDestination: new apigateway.LogGroupLogDestination(
          new logs.LogGroup(this, 'ApiAccessLogs', {
            logGroupName: `/aws/apigateway/echoes-${environment}`,
            retention: logs.RetentionDays.ONE_MONTH,
            removalPolicy: environment === 'prod' ? cdk.RemovalPolicy.RETAIN : cdk.RemovalPolicy.DESTROY,
          })
        ),
        accessLogFormat: apigateway.AccessLogFormat.jsonWithStandardFields(),
      },
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS, // In production, restrict to your frontend URLs
        allowMethods: apigateway.Cors.ALL_METHODS,
        allowHeaders: [
          'Content-Type',
          'X-Amz-Date',
          'Authorization',
          'X-Api-Key',
          'X-Amz-Security-Token',
          'X-Requested-With',
        ],
      },
      policy: new iam.PolicyDocument({
        statements: [
          new iam.PolicyStatement({
            effect: iam.Effect.ALLOW,
            principals: [new iam.AnyPrincipal()],
            actions: ['execute-api:Invoke'],
            resources: ['*'],
          }),
        ],
      }),
    });

    // Cognito Authorizer
    const cognitoAuthorizer = new apigateway.CognitoUserPoolsAuthorizer(this, 'CognitoAuthorizer', {
      cognitoUserPools: [userPool],
      authorizerName: `echoes-authorizer-${environment}`,
      identitySource: 'method.request.header.Authorization',
    });

    // API Resources and Methods
    const echoesResource = this.api.root.addResource('echoes');

    // POST /echoes/init-upload - Generate presigned URL
    const initUploadResource = echoesResource.addResource('init-upload');
    initUploadResource.addMethod('POST', new apigateway.LambdaIntegration(this.initUploadFunction), {
      authorizer: cognitoAuthorizer,
      authorizationType: apigateway.AuthorizationType.COGNITO,
    });

    // POST /echoes - Save echo metadata
    echoesResource.addMethod('POST', new apigateway.LambdaIntegration(this.saveEchoFunction), {
      authorizer: cognitoAuthorizer,
      authorizationType: apigateway.AuthorizationType.COGNITO,
    });

    // GET /echoes - Get echoes with filtering
    echoesResource.addMethod('GET', new apigateway.LambdaIntegration(this.getEchoesFunction), {
      authorizer: cognitoAuthorizer,
      authorizationType: apigateway.AuthorizationType.COGNITO,
      requestParameters: {
        'method.request.querystring.emotion': false,
        'method.request.querystring.limit': false,
        'method.request.querystring.lastEvaluatedKey': false,
        'method.request.querystring.sortBy': false,
        'method.request.querystring.sortOrder': false,
        'method.request.querystring.tags': false,
        'method.request.querystring.startDate': false,
        'method.request.querystring.endDate': false,
      },
    });

    // GET /echoes/random - Get random echo
    const randomResource = echoesResource.addResource('random');
    randomResource.addMethod('GET', new apigateway.LambdaIntegration(this.getRandomEchoFunction), {
      authorizer: cognitoAuthorizer,
      authorizationType: apigateway.AuthorizationType.COGNITO,
      requestParameters: {
        'method.request.querystring.emotion': false,
        'method.request.querystring.excludeRecent': false,
        'method.request.querystring.minDaysOld': false,
        'method.request.querystring.tags': false,
      },
    });

    // Add CloudWatch alarms for monitoring
    const apiErrorAlarm = new cdk.aws_cloudwatch.Alarm(this, 'ApiErrorAlarm', {
      metric: this.api.metricClientError(),
      threshold: 10,
      evaluationPeriods: 2,
      alarmDescription: 'API Gateway 4xx errors exceed threshold',
    });

    const apiLatencyAlarm = new cdk.aws_cloudwatch.Alarm(this, 'ApiLatencyAlarm', {
      metric: this.api.metricLatency(),
      threshold: 5000, // 5 seconds
      evaluationPeriods: 2,
      alarmDescription: 'API Gateway latency exceeds 5 seconds',
    });

    // Lambda function alarms
    [this.initUploadFunction, this.saveEchoFunction, this.getEchoesFunction, this.getRandomEchoFunction].forEach((func, index) => {
      const functionNames = ['InitUpload', 'SaveEcho', 'GetEchoes', 'GetRandomEcho'];
      
      new cdk.aws_cloudwatch.Alarm(this, `${functionNames[index]}ErrorAlarm`, {
        metric: func.metricErrors(),
        threshold: 5,
        evaluationPeriods: 2,
        alarmDescription: `${functionNames[index]} Lambda function errors exceed threshold`,
      });

      new cdk.aws_cloudwatch.Alarm(this, `${functionNames[index]}DurationAlarm`, {
        metric: func.metricDuration(),
        threshold: 10000, // 10 seconds
        evaluationPeriods: 2,
        alarmDescription: `${functionNames[index]} Lambda function duration exceeds 10 seconds`,
      });
    });

    // Add tags
    cdk.Tags.of(this.api).add('Component', 'API');
    cdk.Tags.of(this.initUploadFunction).add('Component', 'Lambda');
    cdk.Tags.of(this.saveEchoFunction).add('Component', 'Lambda');
    cdk.Tags.of(this.getEchoesFunction).add('Component', 'Lambda');
    cdk.Tags.of(this.getRandomEchoFunction).add('Component', 'Lambda');
  }
}