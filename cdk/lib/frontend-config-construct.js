"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.FrontendConfig = void 0;
const cdk = require("aws-cdk-lib");
const constructs_1 = require("constructs");
const ssm = require("aws-cdk-lib/aws-ssm");
const cr = require("aws-cdk-lib/custom-resources");
const lambda = require("aws-cdk-lib/aws-lambda");
const iam = require("aws-cdk-lib/aws-iam");
/**
 * Construct that manages frontend environment configuration
 * Stores configuration in SSM Parameter Store and generates .env files
 */
class FrontendConfig extends constructs_1.Construct {
    constructor(scope, id, props) {
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
    generateEnvContent() {
        const stack = cdk.Stack.of(this);
        const configJson = this.configOutput.value;
        const config = JSON.parse(configJson);
        return Object.entries(config)
            .map(([key, value]) => `${key}=${value}`)
            .join('\n');
    }
}
exports.FrontendConfig = FrontendConfig;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZnJvbnRlbmQtY29uZmlnLWNvbnN0cnVjdC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImZyb250ZW5kLWNvbmZpZy1jb25zdHJ1Y3QudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7O0FBQUEsbUNBQW1DO0FBQ25DLDJDQUF1QztBQUN2QywyQ0FBMkM7QUFDM0MsbURBQW1EO0FBQ25ELGlEQUFpRDtBQUNqRCwyQ0FBMkM7QUFjM0M7OztHQUdHO0FBQ0gsTUFBYSxjQUFlLFNBQVEsc0JBQVM7SUFJM0MsWUFBWSxLQUFnQixFQUFFLEVBQVUsRUFBRSxLQUEwQjtRQUNsRSxLQUFLLENBQUMsS0FBSyxFQUFFLEVBQUUsQ0FBQyxDQUFDO1FBRWpCLE1BQU0sR0FBRyxHQUFHLEtBQUssQ0FBQyxXQUFXLENBQUM7UUFDOUIsTUFBTSxNQUFNLEdBQUcsS0FBSyxDQUFDLE1BQU0sSUFBSSxHQUFHLENBQUMsS0FBSyxDQUFDLEVBQUUsQ0FBQyxJQUFJLENBQUMsQ0FBQyxNQUFNLENBQUM7UUFFekQsZ0VBQWdFO1FBQ2hFLElBQUksQ0FBQyxnQkFBZ0IsR0FBRztZQUN0QixNQUFNLEVBQUUsSUFBSSxHQUFHLENBQUMsZUFBZSxDQUFDLElBQUksRUFBRSxpQkFBaUIsRUFBRTtnQkFDdkQsYUFBYSxFQUFFLFdBQVcsR0FBRyxtQkFBbUI7Z0JBQ2hELFdBQVcsRUFBRSxLQUFLLENBQUMsTUFBTTtnQkFDekIsV0FBVyxFQUFFLDhCQUE4QjthQUM1QyxDQUFDO1lBQ0YsaUJBQWlCLEVBQUUsSUFBSSxHQUFHLENBQUMsZUFBZSxDQUFDLElBQUksRUFBRSw0QkFBNEIsRUFBRTtnQkFDN0UsYUFBYSxFQUFFLFdBQVcsR0FBRyxnQ0FBZ0M7Z0JBQzdELFdBQVcsRUFBRSxLQUFLLENBQUMsaUJBQWlCO2dCQUNwQyxXQUFXLEVBQUUsbUNBQW1DO2FBQ2pELENBQUM7WUFDRixlQUFlLEVBQUUsSUFBSSxHQUFHLENBQUMsZUFBZSxDQUFDLElBQUksRUFBRSwwQkFBMEIsRUFB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QWdCO1lBQzlDLFdBQVcsRUFBRSw2QkFBNkI7WUFDMUMsVUFBVSxFQUFFLEdBQUcsR0FBRyx3QkFBd0I7U0FDM0MsQ0FBQyxDQUFDO1FBRUgsOERBQThEO1FBQzlELElBQUksR0FBRyxDQUFDLFNBQVMsQ0FBQyxJQUFJLEVBQUUsb0JBQW9CLEVBQUU7WUFDNUMsS0FBSyxFQUFFLFdBQVcsR0FBRyxXQUFXO1lBQ2hDLFdBQVcsRUFBRSxxREFBcUQ7WUFDbEUsVUFBVSxFQUFFLEdBQUcsR0FBRyxxQkFBcUI7U0FDeEMsQ0FBQyxDQUFDO0lBQ0wsQ0FBQztJQUVEOztPQUVHO0lBQ0ksa0JBQWtCO1FBQ3ZCLE1BQU0sS0FBSyxHQUFHLEdBQUcsQ0FBQyxLQUFLLENBQUMsRUFBRSxDQUFDLElBQUksQ0FBQyxDQUFDO1FBQ2pDLE1BQU0sVUFBVSxHQUFHLElBQUksQ0FBQyxZQUFZLENBQUMsS0FBSyxDQUFDO1FBQzNDLE1BQU0sTUFBTSxHQUFHLElBQUksQ0FBQyxLQUFLLENBQUMsVUFBVSxDQUFDLENBQUM7UUFFdEMsT0FBTyxNQUFNLENBQUMsT0FBTyxDQUFDLE1BQU0sQ0FBQzthQUMxQixHQUFHLENBQUMsQ0FBQyxDQUFDLEdBQUcsRUFBRSxLQUFLLENBQUMsRUFBRSxFQUFFLENBQUMsR0FBRyxHQUFHLElBQUksS0FBSyxFQUFFLENBQUM7YUFDeEMsSUFBSSxDQUFDLElBQUksQ0FBQyxDQUFDO0lBQ2hCLENBQUM7Q0FDRjtBQTNORCx3Q0EyTkMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgKiBhcyBjZGsgZnJvbSAnYXdzLWNkay1saWInO1xuaW1wb3J0IHsgQ29uc3RydWN0IH0gZnJvbSAnY29uc3RydWN0cyc7XG5pbXBvcnQgKiBhcyBzc20gZnJvbSAnYXdzLWNkay1saWIvYXdzLXNzbSc7XG5pbXBvcnQgKiBhcyBjciBmcm9tICdhd3MtY2RrLWxpYi9jdXN0b20tcmVzb3VyY2VzJztcbmltcG9ydCAqIGFzIGxhbWJkYSBmcm9tICdhd3MtY2RrLWxpYi9hd3MtbGFtYmRhJztcbmltcG9ydCAqIGFzIGlhbSBmcm9tICdhd3MtY2RrLWxpYi9hd3MtaWFtJztcbmltcG9ydCAqIGFzIHBhdGggZnJvbSAncGF0aCc7XG5pbXBvcnQgKiBhcyBmcyBmcm9tICdmcyc7XG5cbmV4cG9ydCBpbnRlcmZhY2UgRnJvbnRlbmRDb25maWdQcm9wcyB7XG4gIGVudmlyb25tZW50OiBzdHJpbmc7XG4gIGFwaVVybDogc3RyaW5nO1xuICBjb2duaXRvVXNlclBvb2xJZDogc3RyaW5nO1xuICBjb2duaXRvQ2xpZW50SWQ6IHN0cmluZztcbiAgczNCdWNrZXROYW1lOiBzdHJpbmc7XG4gIGNsb3VkRnJvbnRVcmw/OiBzdHJpbmc7XG4gIHJlZ2lvbj86IHN0cmluZztcbn1cblxuLyoqXG4gKiBDb25zdHJ1Y3QgdGhhdCBtYW5hZ2VzIGZyb250ZW5kIGVudmlyb25tZW50IGNvbmZpZ3VyYXRpb25cbiAqIFN0b3JlcyBjb25maWd1cmF0aW9uIGluIFNTTSBQYXJhbWV0ZXIgU3RvcmUgYW5kIGdlbmVyYXRlcyAuZW52IGZpbGVzXG4gKi9cbmV4cG9ydCBjbGFzcyBGcm9udGVuZENvbmZpZyBleHRlbmRzIENvbnN0cnVjdCB7XG4gIHB1YmxpYyByZWFkb25seSBjb25maWdQYXJhbWV0ZXJzOiBSZWNvcmQ8c3RyaW5nLCBzc20uU3RyaW5nUGFyYW1ldGVyPjtcbiAgcHVibGljIHJlYWRvbmx5IGNvbmZpZ091dHB1dDogY2RrLkNmbk91dHB1dDtcblxuICBjb25zdHJ1Y3RvcihzY29wZTogQ29uc3RydWN0LCBpZDogc3RyaW5nLCBwcm9wczogRnJvbnRlbmRDb25maWdQcm9wcykge1xuICAgIHN1cGVyKHNjb3BlLCBpZCk7XG5cbiAgICBjb25zdCBlbnYgPSBwcm9wcy5lbnZpcm9ubWVudDtcbiAgICBjb25zdCByZWdpb24gPSBwcm9wcy5yZWdpb24gfHwgY2RrLlN0YWNrLm9mKHRoaXMpLnJlZ2lvbjtcblxuICAgIC8vIFN0b3JlIGNvbmZpZ3VyYXRpb24gaW4gU1NNIFBhcmFtZXRlciBTdG9yZSBmb3IgcnVudGltZSBhY2Nlc3NcbiAgICB0aGlzLmNvbmZpZ1BhcmFtZXRlcnMgPSB7XG4gICAgICBhcGlVcmw6IG5ldyBzc20uU3RyaW5nUGFyYW1ldGVyKHRoaXMsICdBcGlVcmxQYXJhbWV0ZXInLCB7XG4gICAgICAgIHBhcmFtZXRlck5hbWU6IGAvZWNob2VzLyR7ZW52fS9mcm9udGVuZC9hcGktdXJsYCxcbiAgICAgICAgc3RyaW5nVmFsdWU6IHByb3BzLmFwaVVybCxcbiAgICAgICAgZGVzY3JpcHRpb246ICdBUEkgR2F0ZXdheSBVUkwgZm9yIGZyb250ZW5kJyxcbiAgICAgIH0pLFxuICAgICAgY29nbml0b1VzZXJQb29sSWQ6IG5ldyBzc20uU3RyaW5nUGFyYW1ldGVyKHRoaXMsICdDb2duaXRvVXNlclBvb2xJZFBhcmFtZXRlcicsIHtcbiAgICAgICAgcGFyYW1ldGVyTmFtZTogYC9lY2hvZXMvJHtlbnZ9L2Zyb250ZW5kL2NvZ25pdG8tdXNlci1wb29sLWlkYCxcbiAgICAgICAgc3RyaW5nVmFsdWU6IHByb3BzLmNvZ25pdG9Vc2VyUG9vbElkLFxuICAgICAgICBkZXNjcmlwdGlvbjogJ0NvZ25pdG8gVXNlciBQb29sIElEIGZvciBmcm9udGVuZCcsXG4gICAgICB9KSxcbiAgICAgIGNvZ25pdG9DbGllbnRJZDogbmV3IHNzbS5TdHJpbmdQYXJhbWV0ZXIodGhpcywgJ0NvZ25pdG9DbGllbnRJZFBhcmFtZXRlcicsIHtcbiAgICAgICAgcGFyYW1ldGVyTmFtZTogYC9lY2hvZXMvJHtlbnZ9L2Zyb250ZW5kL2NvZ25pdG8tY2xpZW50LWlkYCxcbiAgICAgICAgc3RyaW5nVmFsdWU6IHByb3BzLmNvZ25pdG9DbGllbnRJZCxcbiAgICAgICAgZGVzY3JpcHRpb246ICdDb2duaXRvIENsaWVudCBJRCBmb3IgZnJvbnRlbmQnLFxuICAgICAgfSksXG4gICAgICBzM0J1Y2tldE5hbWU6IG5ldyBzc20uU3RyaW5nUGFyYW1ldGVyKHRoaXMsICdTM0J1Y2tldE5hbWVQYXJhbWV0ZXInLCB7XG4gICAgICAgIHBhcmFtZXRlck5hbWU6IGAvZWNob2VzLyR7ZW52fS9mcm9udGVuZC9zMy1idWNrZXRgLFxuICAgICAgICBzdHJpbmdWYWx1ZTogcHJvcHMuczNCdWNrZXROYW1lLFxuICAgICAgICBkZXNjcmlwdGlvbjogJ1MzIGJ1Y2tldCBuYW1lIGZvciBhdWRpbyB1cGxvYWRzJyxcbiAgICAgIH0pLFxuICAgICAgY2xvdWRGcm9udFVybDogbmV3IHNzbS5TdHJpbmdQYXJhbWV0ZXIodGhpcywgJ0Nsb3VkRnJvbnRVcmxQYXJhbWV0ZXInLCB7XG4gICAgICAgIHBhcmFtZXRlck5hbWU6IGAvZWNob2VzLyR7ZW52fS9mcm9udGVuZC9jbG91ZGZyb250LXVybGAsXG4gICAgICAgIHN0cmluZ1ZhbHVlOiBwcm9wcy5jbG91ZEZyb250VXJsIHx8ICcnLFxuICAgICAgICBkZXNjcmlwdGlvbjogJ0Nsb3VkRnJvbnQgZGlzdHJpYnV0aW9uIFVSTCcsXG4gICAgICB9KSxcbiAgICAgIHJlZ2lvbjogbmV3IHNzbS5TdHJpbmdQYXJhbWV0ZXIodGhpcywgJ1JlZ2lvblBhcmFtZXRlcicsIHtcbiAgICAgICAgcGFyYW1ldGVyTmFtZTogYC9lY2hvZXMvJHtlbnZ9L2Zyb250ZW5kL3JlZ2lvbmAsXG4gICAgICAgIHN0cmluZ1ZhbHVlOiByZWdpb24sXG4gICAgICAgIGRlc2NyaXB0aW9uOiAnQVdTIHJlZ2lvbiBmb3IgZnJvbnRlbmQgc2VydmljZXMnLFxuICAgICAgfSksXG4gICAgfTtcblxuICAgIC8vIENyZWF0ZSBhIGN1c3RvbSByZXNvdXJjZSB0byBnZW5lcmF0ZSAuZW52IGZpbGVcbiAgICBjb25zdCBlbnZHZW5lcmF0b3JGdW5jdGlvbiA9IG5ldyBsYW1iZGEuRnVuY3Rpb24odGhpcywgJ0VudkdlbmVyYXRvckZ1bmN0aW9uJywge1xuICAgICAgcnVudGltZTogbGFtYmRhLlJ1bnRpbWUuTk9ERUpTXzE4X1gsXG4gICAgICBoYW5kbGVyOiAnaW5kZXguaGFuZGxlcicsXG4gICAgICBjb2RlOiBsYW1iZGEuQ29kZS5mcm9tSW5saW5lKGBcbiAgICAgICAgY29uc3QgeyBTU01DbGllbnQsIEdldFBhcmFtZXRlcnNCeVBhdGhDb21tYW5kIH0gPSByZXF1aXJlKCdAYXdzLXNkay9jbGllbnQtc3NtJyk7XG4gICAgICAgIGNvbnN0IHJlc3BvbnNlID0gcmVxdWlyZSgnY2ZuLXJlc3BvbnNlLWFzeW5jJyk7XG4gICAgICAgIFxuICAgICAgICBleHBvcnRzLmhhbmRsZXIgPSBhc3luYyAoZXZlbnQsIGNvbnRleHQpID0+IHtcbiAgICAgICAgICBjb25zb2xlLmxvZygnRXZlbnQ6JywgSlNPTi5zdHJpbmdpZnkoZXZlbnQpKTtcbiAgICAgICAgICBcbiAgICAgICAgICBpZiAoZXZlbnQuUmVxdWVzdFR5cGUgPT09ICdEZWxldGUnKSB7XG4gICAgICAgICAgICBhd2FpdCByZXNwb25zZS5zZW5kKGV2ZW50LCBjb250ZXh0LCByZXNwb25zZS5TVUNDRVNTLCB7fSk7XG4gICAgICAgICAgICByZXR1cm47XG4gICAgICAgICAgfVxuICAgICAgICAgIFxuICAgICAgICAgIHRyeSB7XG4gICAgICAgICAgICBjb25zdCBzc21DbGllbnQgPSBuZXcgU1NNQ2xpZW50KHsgcmVnaW9uOiBldmVudC5SZXNvdXJjZVByb3BlcnRpZXMuUmVnaW9uIH0pO1xuICAgICAgICAgICAgY29uc3QgcGFyYW1ldGVyUGF0aCA9IGV2ZW50LlJlc291cmNlUHJvcGVydGllcy5QYXJhbWV0ZXJQYXRoO1xuICAgICAgICAgICAgXG4gICAgICAgICAgICAvLyBHZXQgYWxsIHBhcmFtZXRlcnMgdW5kZXIgdGhlIHBhdGhcbiAgICAgICAgICAgIGNvbnN0IGNvbW1hbmQgPSBuZXcgR2V0UGFyYW1ldGVyc0J5UGF0aENvbW1hbmQoe1xuICAgICAgICAgICAgICBQYXRoOiBwYXJhbWV0ZXJQYXRoLFxuICAgICAgICAgICAgICBSZWN1cnNpdmU6IGZhbHNlLFxuICAgICAgICAgICAgICBXaXRoRGVjcnlwdGlvbjogdHJ1ZSxcbiAgICAgICAgICAgIH0pO1xuICAgICAgICAgICAgXG4gICAgICAgICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBzc21DbGllbnQuc2VuZChjb21tYW5kKTtcbiAgICAgICAgICAgIFxuICAgICAgICAgICAgLy8gQnVpbGQgZW52aXJvbm1lbnQgY29uZmlndXJhdGlvblxuICAgICAgICAgICAgY29uc3QgZW52Q29uZmlnID0ge1xuICAgICAgICAgICAgICBWSVRFX0FQSV9VUkw6ICcnLFxuICAgICAgICAgICAgICBWSVRFX0NPR05JVE9fVVNFUl9QT09MX0lEOiAnJyxcbiAgICAgICAgICAgICAgVklURV9DT0dOSVRPX0NMSUVOVF9JRDogJycsXG4gICAgICAgICAgICAgIFZJVEVfUzNfQlVDS0VUOiAnJyxcbiAgICAgICAgICAgICAgVklURV9TM19SRUdJT046IGV2ZW50LlJlc291cmNlUHJvcGVydGllcy5SZWdpb24sXG4gICAgICAgICAgICAgIFZJVEVfQ09HTklUT19SRUdJT046IGV2ZW50LlJlc291cmNlUHJvcGVydGllcy5SZWdpb24sXG4gICAgICAgICAgICB9O1xuICAgICAgICAgICAgXG4gICAgICAgICAgICAvLyBNYXAgU1NNIHBhcmFtZXRlcnMgdG8gZW52IHZhcmlhYmxlc1xuICAgICAgICAgICAgcmVzdWx0LlBhcmFtZXRlcnMuZm9yRWFjaChwYXJhbSA9PiB7XG4gICAgICAgICAgICAgIGNvbnN0IGtleSA9IHBhcmFtLk5hbWUuc3BsaXQoJy8nKS5wb3AoKTtcbiAgICAgICAgICAgICAgc3dpdGNoKGtleSkge1xuICAgICAgICAgICAgICAgIGNhc2UgJ2FwaS11cmwnOlxuICAgICAgICAgICAgICAgICAgZW52Q29uZmlnLlZJVEVfQVBJX1VSTCA9IHBhcmFtLlZhbHVlO1xuICAgICAgICAgICAgICAgICAgYnJlYWs7XG4gICAgICAgICAgICAgICAgY2FzZSAnY29nbml0by11c2VyLXBvb2wtaWQnOlxuICAgICAgICAgICAgICAgICAgZW52Q29uZmlnLlZJVEVfQ09HTklUT19VU0VSX1BPT0xfSUQgPSBwYXJhbS5WYWx1ZTtcbiAgICAgICAgICAgICAgICAgIGJyZWFrO1xuICAgICAgICAgICAgICAgIGNhc2UgJ2NvZ25pdG8tY2xpZW50LWlkJzpcbiAgICAgICAgICAgICAgICAgIGVudkNvbmZpZy5WSVRFX0NPR05JVE9fQ0xJRU5UX0lEID0gcGFyYW0uVmFsdWU7XG4gICAgICAgICAgICAgICAgICBicmVhaztcbiAgICAgICAgICAgICAgICBjYXNlICdzMy1idWNrZXQnOlxuICAgICAgICAgICAgICAgICAgZW52Q29uZmlnLlZJVEVfUzNfQlVDS0VUID0gcGFyYW0uVmFsdWU7XG4gICAgICAgICAgICAgICAgICBicmVhaztcbiAgICAgICAgICAgICAgICBjYXNlICdjbG91ZGZyb250LXVybCc6XG4gICAgICAgICAgICAgICAgICBlbnZDb25maWcuVklURV9DTE9VREZST05UX1VSTCA9IHBhcmFtLlZhbHVlO1xuICAgICAgICAgICAgICAgICAgYnJlYWs7XG4gICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH0pO1xuICAgICAgICAgICAgXG4gICAgICAgICAgICAvLyBHZW5lcmF0ZSAuZW52IGNvbnRlbnRcbiAgICAgICAgICAgIGNvbnN0IGVudkNvbnRlbnQgPSBPYmplY3QuZW50cmllcyhlbnZDb25maWcpXG4gICAgICAgICAgICAgIC5tYXAoKFtrZXksIHZhbHVlXSkgPT4gXFxgXFwke2tleX09XFwke3ZhbHVlfVxcYClcbiAgICAgICAgICAgICAgLmpvaW4oJ1xcXFxuJyk7XG4gICAgICAgICAgICBcbiAgICAgICAgICAgIGF3YWl0IHJlc3BvbnNlLnNlbmQoZXZlbnQsIGNvbnRleHQsIHJlc3BvbnNlLlNVQ0NFU1MsIHtcbiAgICAgICAgICAgICAgRGF0YToge1xuICAgICAgICAgICAgICAgIEVudkNvbnRlbnQ6IGVudkNvbnRlbnQsXG4gICAgICAgICAgICAgICAgQ29uZmlnOiBKU09OLnN0cmluZ2lmeShlbnZDb25maWcpLFxuICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9KTtcbiAgICAgICAgICB9IGNhdGNoIChlcnJvcikge1xuICAgICAgICAgICAgY29uc29sZS5lcnJvcignRXJyb3I6JywgZXJyb3IpO1xuICAgICAgICAgICAgYXdhaXQgcmVzcG9uc2Uuc2VuZChldmVudCwgY29udGV4dCwgcmVzcG9uc2UuRkFJTEVELCB7fSk7XG4gICAgICAgICAgfVxuICAgICAgICB9O1xuICAgICAgYCksXG4gICAgICB0aW1lb3V0OiBjZGsuRHVyYXRpb24ubWludXRlcygxKSxcbiAgICAgIG1lbW9yeVNpemU6IDEyOCxcbiAgICB9KTtcblxuICAgIC8vIEdyYW50IHRoZSBMYW1iZGEgZnVuY3Rpb24gcGVybWlzc2lvbiB0byByZWFkIFNTTSBwYXJhbWV0ZXJzXG4gICAgZW52R2VuZXJhdG9yRnVuY3Rpb24uYWRkVG9Sb2xlUG9saWN5KG5ldyBpYW0uUG9saWN5U3RhdGVtZW50KHtcbiAgICAgIGFjdGlvbnM6IFsnc3NtOkdldFBhcmFtZXRlcnNCeVBhdGgnXSxcbiAgICAgIHJlc291cmNlczogW2Bhcm46YXdzOnNzbToke3JlZ2lvbn06KjpwYXJhbWV0ZXIvZWNob2VzLyR7ZW52fS9mcm9udGVuZC8qYF0sXG4gICAgfSkpO1xuXG4gICAgLy8gQ3JlYXRlIGN1c3RvbSByZXNvdXJjZVxuICAgIGNvbnN0IGVudkdlbmVyYXRvciA9IG5ldyBjci5Bd3NDdXN0b21SZXNvdXJjZSh0aGlzLCAnRW52R2VuZXJhdG9yJywge1xuICAgICAgb25DcmVhdGU6IHtcbiAgICAgICAgc2VydmljZTogJ0xhbWJkYScsXG4gICAgICAgIGFjdGlvbjogJ2ludm9rZScsXG4gICAgICAgIHBhcmFtZXRlcnM6IHtcbiAgICAgICAgICBGdW5jdGlvbk5hbWU6IGVudkdlbmVyYXRvckZ1bmN0aW9uLmZ1bmN0aW9uTmFtZSxcbiAgICAgICAgICBQYXlsb2FkOiBKU09OLnN0cmluZ2lmeSh7XG4gICAgICAgICAgICBSZXF1ZXN0VHlwZTogJ0NyZWF0ZScsXG4gICAgICAgICAgICBSZXNvdXJjZVByb3BlcnRpZXM6IHtcbiAgICAgICAgICAgICAgUGFyYW1ldGVyUGF0aDogYC9lY2hvZXMvJHtlbnZ9L2Zyb250ZW5kYCxcbiAgICAgICAgICAgICAgUmVnaW9uOiByZWdpb24sXG4gICAgICAgICAgICB9LFxuICAgICAgICAgIH0pLFxuICAgICAgICB9LFxuICAgICAgICBwaHlzaWNhbFJlc291cmNlSWQ6IGNyLlBoeXNpY2FsUmVzb3VyY2VJZC5vZignZnJvbnRlbmQtZW52LWdlbmVyYXRvcicpLFxuICAgICAgfSxcbiAgICAgIG9uVXBkYXRlOiB7XG4gICAgICAgIHNlcnZpY2U6ICdMYW1iZGEnLFxuICAgICAgICBhY3Rpb246ICdpbnZva2UnLFxuICAgICAgICBwYXJhbWV0ZXJzOiB7XG4gICAgICAgICAgRnVuY3Rpb25OYW1lOiBlbnZHZW5lcmF0b3JGdW5jdGlvbi5mdW5jdGlvbk5hbWUsXG4gICAgICAgICAgUGF5bG9hZDogSlNPTi5zdHJpbmdpZnkoe1xuICAgICAgICAgICAgUmVxdWVzdFR5cGU6ICdVcGRhdGUnLFxuICAgICAgICAgICAgUmVzb3VyY2VQcm9wZXJ0aWVzOiB7XG4gICAgICAgICAgICAgIFBhcmFtZXRlclBhdGg6IGAvZWNob2VzLyR7ZW52fS9mcm9udGVuZGAsXG4gICAgICAgICAgICAgIFJlZ2lvbjogcmVnaW9uLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICB9KSxcbiAgICAgICAgfSxcbiAgICAgIH0sXG4gICAgICBwb2xpY3k6IGNyLkF3c0N1c3RvbVJlc291cmNlUG9saWN5LmZyb21TdGF0ZW1lbnRzKFtcbiAgICAgICAgbmV3IGlhbS5Qb2xpY3lTdGF0ZW1lbnQoe1xuICAgICAgICAgIGFjdGlvbnM6IFsnbGFtYmRhOkludm9rZUZ1bmN0aW9uJ10sXG4gICAgICAgICAgcmVzb3VyY2VzOiBbZW52R2VuZXJhdG9yRnVuY3Rpb24uZnVuY3Rpb25Bcm5dLFxuICAgICAgICB9KSxcbiAgICAgIF0pLFxuICAgIH0pO1xuXG4gICAgLy8gT3V0cHV0IHRoZSBjb25maWd1cmF0aW9uIGFzIEpTT05cbiAgICB0aGlzLmNvbmZpZ091dHB1dCA9IG5ldyBjZGsuQ2ZuT3V0cHV0KHRoaXMsICdGcm9udGVuZENvbmZpZ0pzb24nLCB7XG4gICAgICB2YWx1ZTogSlNPTi5zdHJpbmdpZnkoe1xuICAgICAgICBWSVRFX0FQSV9VUkw6IHByb3BzLmFwaVVybCxcbiAgICAgICAgVklURV9DT0dOSVRPX1VTRVJfUE9PTF9JRDogcHJvcHMuY29nbml0b1VzZXJQb29sSWQsXG4gICAgICAgIFZJVEVfQ09HTklUT19DTElFTlRfSUQ6IHByb3BzLmNvZ25pdG9DbGllbnRJZCxcbiAgICAgICAgVklURV9TM19CVUNLRVQ6IHByb3BzLnMzQnVja2V0TmFtZSxcbiAgICAgICAgVklURV9TM19SRUdJT046IHJlZ2lvbixcbiAgICAgICAgVklURV9DT0dOSVRPX1JFR0lPTjogcmVnaW9uLFxuICAgICAgICBWSVRFX0NMT1VERlJPTlRfVVJMOiBwcm9wcy5jbG91ZEZyb250VXJsIHx8ICcnLFxuICAgICAgfSksXG4gICAgICBkZXNjcmlwdGlvbjogJ0Zyb250ZW5kIGNvbmZpZ3VyYXRpb24gYXMgSlNPTicsXG4gICAgICBleHBvcnROYW1lOiBgJHtlbnZ9LUZyb250ZW5kQ29uZmlnYCxcbiAgICB9KTtcblxuICAgIC8vIE91dHB1dCBpbmRpdmlkdWFsIGNvbmZpZ3VyYXRpb24gdmFsdWVzIGZvciBlYXN5IGFjY2Vzc1xuICAgIG5ldyBjZGsuQ2ZuT3V0cHV0KHRoaXMsICdGcm9udGVuZEFwaVVybCcsIHtcbiAgICAgIHZhbHVlOiBwcm9wcy5hcGlVcmwsXG4gICAgICBkZXNjcmlwdGlvbjogJ0FQSSBVUkwgZm9yIGZyb250ZW5kJyxcbiAgICAgIGV4cG9ydE5hbWU6IGAke2Vudn0tRnJvbnRlbmRBcGlVcmxgLFxuICAgIH0pO1xuXG4gICAgbmV3IGNkay5DZm5PdXRwdXQodGhpcywgJ0Zyb250ZW5kQ2xvdWRGcm9udFVybCcsIHtcbiAgICAgIHZhbHVlOiBwcm9wcy5jbG91ZEZyb250VXJsIHx8ICdOb3QgY29uZmlndXJlZCcsXG4gICAgICBkZXNjcmlwdGlvbjogJ0Nsb3VkRnJvbnQgVVJMIGZvciBmcm9udGVuZCcsXG4gICAgICBleHBvcnROYW1lOiBgJHtlbnZ9LUZyb250ZW5kQ2xvdWRGcm9udFVybGAsXG4gICAgfSk7XG5cbiAgICAvLyBPdXRwdXQgdGhlIFNTTSBwYXJhbWV0ZXIgcGF0aCBmb3IgdXNlIGluIGRlcGxveW1lbnQgc2NyaXB0c1xuICAgIG5ldyBjZGsuQ2ZuT3V0cHV0KHRoaXMsICdGcm9udGVuZENvbmZpZ1BhdGgnLCB7XG4gICAgICB2YWx1ZTogYC9lY2hvZXMvJHtlbnZ9L2Zyb250ZW5kYCxcbiAgICAgIGRlc2NyaXB0aW9uOiAnU1NNIFBhcmFtZXRlciBTdG9yZSBwYXRoIGZvciBmcm9udGVuZCBjb25maWd1cmF0aW9uJyxcbiAgICAgIGV4cG9ydE5hbWU6IGAke2Vudn0tRnJvbnRlbmRDb25maWdQYXRoYCxcbiAgICB9KTtcbiAgfVxuXG4gIC8qKlxuICAgKiBHZW5lcmF0ZSBhIC5lbnYgZmlsZSBjb250ZW50IHN0cmluZyBmcm9tIHRoZSBjb25maWd1cmF0aW9uXG4gICAqL1xuICBwdWJsaWMgZ2VuZXJhdGVFbnZDb250ZW50KCk6IHN0cmluZyB7XG4gICAgY29uc3Qgc3RhY2sgPSBjZGsuU3RhY2sub2YodGhpcyk7XG4gICAgY29uc3QgY29uZmlnSnNvbiA9IHRoaXMuY29uZmlnT3V0cHV0LnZhbHVlO1xuICAgIGNvbnN0IGNvbmZpZyA9IEpTT04ucGFyc2UoY29uZmlnSnNvbik7XG5cbiAgICByZXR1cm4gT2JqZWN0LmVudHJpZXMoY29uZmlnKVxuICAgICAgLm1hcCgoW2tleSwgdmFsdWVdKSA9PiBgJHtrZXl9PSR7dmFsdWV9YClcbiAgICAgIC5qb2luKCdcXG4nKTtcbiAgfVxufSJdfQ==