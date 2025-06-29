import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import { Construct } from 'constructs';
export interface EchoesStorageStackProps extends cdk.StackProps {
    environment: string;
}
export declare class EchoesStorageStack extends cdk.Stack {
    readonly audioBucket: s3.Bucket;
    readonly echoesTable: dynamodb.Table;
    constructor(scope: Construct, id: string, props: EchoesStorageStackProps);
}
