import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
export interface FrontendStackProps extends cdk.StackProps {
    environment: string;
}
export declare class EchoesFrontendStack extends cdk.Stack {
    readonly websiteBucket: s3.Bucket;
    readonly bucketWebsiteUrl: string;
    readonly originAccessIdentity: cloudfront.OriginAccessIdentity;
    constructor(scope: Construct, id: string, props: FrontendStackProps);
}
