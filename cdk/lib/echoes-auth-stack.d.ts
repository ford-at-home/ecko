import * as cdk from 'aws-cdk-lib';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import { Construct } from 'constructs';
export interface EchoesAuthStackProps extends cdk.StackProps {
    environment: string;
}
export declare class EchoesAuthStack extends cdk.Stack {
    readonly userPool: cognito.UserPool;
    readonly userPoolClient: cognito.UserPoolClient;
    readonly identityPool: cognito.CfnIdentityPool;
    constructor(scope: Construct, id: string, props: EchoesAuthStackProps);
}
