import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import * as cr from 'aws-cdk-lib/custom-resources';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as path from 'path';
import * as fs from 'fs';

export interface FrontendConfigProps {
  environment: string;
  apiUrl: string;
  cognitoUserPoolId: string;
  cognitoClientId: string;
  s3BucketName: string;
  cloudFrontUrl?: string;
  region?: string;
}

/**
 * Construct that manages frontend environment configuration
 * Stores configuration in SSM Parameter Store and generates .env files
 */
export class FrontendConfig extends Construct {
  public readonly configParameters: Record<string, ssm.StringParameter>;
  public readonly configOutput: cdk.CfnOutput;

  constructor(scope: Construct, id: string, props: FrontendConfigProps) {
    super(scope, id);

    const env = props.environment;
    const region = props.region || cdk.Stack.of(this).region;

    // Store configuration in SSM Parameter Store for runtime access
    this.configParameters = {
      apiUrl: new ssm.StringParameter(this, 'ApiUrlParameter', {
        parameterName: `/echoes/${env}/frontend/api-url`,
        stringValue: props.apiUrl,
        description: 'API Gateway URL for frontend',
      }),
      cognitoUserPoolId: new ssm.StringParameter(this, 'CognitoUserPoolIdParameter', {
        parameterName: `/echoes/${env}/frontend/cognito-user-pool-id`,
        stringValue: props.cognitoUserPoolId,
        description: 'Cognito User Pool ID for frontend',
      }),
      cognitoClientId: new ssm.StringParameter(this, 'CognitoClientIdParameter', {
        parameterName: `/echoes/${env}/frontend/cognito-client-id`,
        stringValue: props.cognitoClientId,
        description: 'Cognito Client ID for frontend',
      }),
      s3BucketName: new ssm.StringParameter(this, 'S3BucketNameParameter', {
        parameterName: `/echoes/${env}/frontend/s3-bucket`,
        stringValue: props.s3BucketName,
        description: 'S3 bucket name for audio uploads',
      }),
      cloudFrontUrl: new ssm.StringParameter(this, 'CloudFrontUrlParameter', {
        parameterName: `/echoes/${env}/frontend/cloudfront-url`,
        stringValue: props.cloudFrontUrl || '',
        description: 'CloudFront distribution URL',
      }),
      region: new ssm.StringParameter(this, 'RegionParameter', {
        parameterName: `/echoes/${env}/frontend/region`,
        stringValue: region,
        description: 'AWS region for frontend services',
      }),
    };

    // Create a custom resource to generate .env file
    const envGeneratorFunction = new lambda.Function(this, 'EnvGeneratorFunction', {
      runtime: lambda.Runtime.NODEJS_18_X,
      handler: 'index.handler',
      code: lambda.Code.fromInline(`
        const { SSMClient, GetParametersByPathCommand } = require('@aws-sdk/client-ssm');
        const response = require('cfn-response-async');
        
        exports.handler = async (event, context) => {
          console.log('Event:', JSON.stringify(event));
          
          if (event.RequestType === 'Delete') {
            await response.send(event, context, response.SUCCESS, {});
            return;
          }
          
          try {
            const ssmClient = new SSMClient({ region: event.ResourceProperties.Region });
            const parameterPath = event.ResourceProperties.ParameterPath;
            
            // Get all parameters under the path
            const command = new GetParametersByPathCommand({
              Path: parameterPath,
              Recursive: false,
              WithDecryption: true,
            });
            
            const result = await ssmClient.send(command);
            
            // Build environment configuration
            const envConfig = {
              VITE_API_URL: '',
              VITE_COGNITO_USER_POOL_ID: '',
              VITE_COGNITO_CLIENT_ID: '',
              VITE_S3_BUCKET: '',
              VITE_S3_REGION: event.ResourceProperties.Region,
              VITE_COGNITO_REGION: event.ResourceProperties.Region,
            };
            
            // Map SSM parameters to env variables
            result.Parameters.forEach(param => {
              const key = param.Name.split('/').pop();
              switch(key) {
                case 'api-url':
                  envConfig.VITE_API_URL = param.Value;
                  break;
                case 'cognito-user-pool-id':
                  envConfig.VITE_COGNITO_USER_POOL_ID = param.Value;
                  break;
                case 'cognito-client-id':
                  envConfig.VITE_COGNITO_CLIENT_ID = param.Value;
                  break;
                case 's3-bucket':
                  envConfig.VITE_S3_BUCKET = param.Value;
                  break;
                case 'cloudfront-url':
                  envConfig.VITE_CLOUDFRONT_URL = param.Value;
                  break;
              }
            });
            
            // Generate .env content
            const envContent = Object.entries(envConfig)
              .map(([key, value]) => \`\${key}=\${value}\`)
              .join('\\n');
            
            await response.send(event, context, response.SUCCESS, {
              Data: {
                EnvContent: envContent,
                Config: JSON.stringify(envConfig),
              }
            });
          } catch (error) {
            console.error('Error:', error);
            await response.send(event, context, response.FAILED, {});
          }
        };
      `),
      timeout: cdk.Duration.minutes(1),
      memorySize: 128,
    });

    // Grant the Lambda function permission to read SSM parameters
    envGeneratorFunction.addToRolePolicy(new iam.PolicyStatement({
      actions: ['ssm:GetParametersByPath'],
      resources: [`arn:aws:ssm:${region}:*:parameter/echoes/${env}/frontend/*`],
    }));

    // Create custom resource
    const envGenerator = new cr.AwsCustomResource(this, 'EnvGenerator', {
      onCreate: {
        service: 'Lambda',
        action: 'invoke',
        parameters: {
          FunctionName: envGeneratorFunction.functionName,
          Payload: JSON.stringify({
            RequestType: 'Create',
            ResourceProperties: {
              ParameterPath: `/echoes/${env}/frontend`,
              Region: region,
            },
          }),
        },
        physicalResourceId: cr.PhysicalResourceId.of('frontend-env-generator'),
      },
      onUpdate: {
        service: 'Lambda',
        action: 'invoke',
        parameters: {
          FunctionName: envGeneratorFunction.functionName,
          Payload: JSON.stringify({
            RequestType: 'Update',
            ResourceProperties: {
              ParameterPath: `/echoes/${env}/frontend`,
              Region: region,
            },
          }),
        },
      },
      policy: cr.AwsCustomResourcePolicy.fromStatements([
        new iam.PolicyStatement({
          actions: ['lambda:InvokeFunction'],
          resources: [envGeneratorFunction.functionArn],
        }),
      ]),
    });

    // Output the configuration as JSON
    this.configOutput = new cdk.CfnOutput(this, 'FrontendConfigJson', {
      value: JSON.stringify({
        VITE_API_URL: props.apiUrl,
        VITE_COGNITO_USER_POOL_ID: props.cognitoUserPoolId,
        VITE_COGNITO_CLIENT_ID: props.cognitoClientId,
        VITE_S3_BUCKET: props.s3BucketName,
        VITE_S3_REGION: region,
        VITE_COGNITO_REGION: region,
        VITE_CLOUDFRONT_URL: props.cloudFrontUrl || '',
      }),
      description: 'Frontend configuration as JSON',
      exportName: `${env}-FrontendConfig`,
    });

    // Output individual configuration values for easy access
    new cdk.CfnOutput(this, 'FrontendApiUrl', {
      value: props.apiUrl,
      description: 'API URL for frontend',
      exportName: `${env}-FrontendApiUrl`,
    });

    new cdk.CfnOutput(this, 'FrontendCloudFrontUrl', {
      value: props.cloudFrontUrl || 'Not configured',
      description: 'CloudFront URL for frontend',
      exportName: `${env}-FrontendCloudFrontUrl`,
    });

    // Output the SSM parameter path for use in deployment scripts
    new cdk.CfnOutput(this, 'FrontendConfigPath', {
      value: `/echoes/${env}/frontend`,
      description: 'SSM Parameter Store path for frontend configuration',
      exportName: `${env}-FrontendConfigPath`,
    });
  }

  /**
   * Generate a .env file content string from the configuration
   */
  public generateEnvContent(): string {
    const stack = cdk.Stack.of(this);
    const configJson = this.configOutput.value;
    const config = JSON.parse(configJson);

    return Object.entries(config)
      .map(([key, value]) => `${key}=${value}`)
      .join('\n');
  }
}