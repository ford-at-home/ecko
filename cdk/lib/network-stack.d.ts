import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as s3 from 'aws-cdk-lib/aws-s3';
export interface NetworkStackProps extends cdk.StackProps {
    frontendBucket: s3.Bucket;
    originAccessIdentity: cloudfront.OriginAccessIdentity;
    environment: string;
    domainName?: string;
}
export declare class EchoesNetworkStack extends cdk.Stack {
    readonly distribution: cloudfront.Distribution;
    readonly distributionUrl: string;
    constructor(scope: Construct, id: string, props: NetworkStackProps);
}
