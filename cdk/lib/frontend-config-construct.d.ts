import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as ssm from 'aws-cdk-lib/aws-ssm';
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
export declare class FrontendConfig extends Construct {
    readonly configParameters: Record<string, ssm.StringParameter>;
    readonly configOutput: cdk.CfnOutput;
    constructor(scope: Construct, id: string, props: FrontendConfigProps);
    /**
     * Generate a .env file content string from the configuration
     */
    generateEnvContent(): string;
}
