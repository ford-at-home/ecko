import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import { Construct } from 'constructs';
export interface EchoesApiStackProps extends cdk.StackProps {
    environment: string;
    bucket: s3.Bucket;
    table: dynamodb.Table;
    userPool: cognito.UserPool;
    userPoolClient: cognito.UserPoolClient;
}
export declare class EchoesApiStack extends cdk.Stack {
    readonly api: apigateway.RestApi;
    readonly lambdaFunction: lambda.Function;
    readonly apiUrl: string;
    constructor(scope: Construct, id: string, props: EchoesApiStackProps);
}
