import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as path from 'path';

export interface FrontendStackProps extends cdk.StackProps {
  environment: string;
}

export class EchoesFrontendStack extends cdk.Stack {
  public readonly websiteBucket: s3.Bucket;
  public readonly bucketWebsiteUrl: string;
  public readonly originAccessIdentity: cloudfront.OriginAccessIdentity;

  constructor(scope: Construct, id: string, props: FrontendStackProps) {
    super(scope, id, props);

    const env = props.environment;

    // Create S3 bucket for frontend hosting
    this.websiteBucket = new s3.Bucket(this, 'WebsiteBucket', {
      bucketName: `echoes-frontend-${env}-${this.account}`,
      websiteIndexDocument: 'index.html',
      websiteErrorDocument: 'index.html', // For SPA routing
      publicReadAccess: false, // Changed to false since we're using CloudFront OAI
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL, // Block all public access
      cors: [
        {
          allowedMethods: [
            s3.HttpMethods.GET,
            s3.HttpMethods.HEAD,
          ],
          allowedOrigins: ['*'],
          allowedHeaders: ['*'],
          maxAge: 3000,
        },
      ],
      removalPolicy: env === 'prod' 
        ? cdk.RemovalPolicy.RETAIN 
        : cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: env !== 'prod', // Only auto-delete in non-prod
    });

    // Create CloudFront Origin Access Identity
    this.originAccessIdentity = new cloudfront.OriginAccessIdentity(this, 'OAI', {
      comment: `OAI for Echoes ${env} frontend`
    });

    // Grant CloudFront OAI access to the bucket
    this.websiteBucket.grantRead(this.originAccessIdentity);

    // Deploy frontend build files if they exist
    const frontendBuildPath = path.join(__dirname, '..', '..', '..', 'frontend', 'dist');
    
    // Only deploy if build directory exists
    try {
      new s3deploy.BucketDeployment(this, 'DeployWebsite', {
        sources: [s3deploy.Source.asset(frontendBuildPath)],
        destinationBucket: this.websiteBucket,
        prune: true, // Remove old files
        retainOnDelete: false,
      });
    } catch (error) {
      console.log('Frontend build directory not found. Skipping deployment.');
      console.log('Run "npm run build" in the frontend directory before deploying.');
    }

    // Store the website URL
    this.bucketWebsiteUrl = this.websiteBucket.bucketWebsiteUrl;

    // Outputs
    new cdk.CfnOutput(this, 'WebsiteBucketName', {
      value: this.websiteBucket.bucketName,
      description: 'Frontend S3 bucket name',
      exportName: `${env}-WebsiteBucketName`,
    });

    new cdk.CfnOutput(this, 'WebsiteBucketArn', {
      value: this.websiteBucket.bucketArn,
      description: 'Frontend S3 bucket ARN',
      exportName: `${env}-WebsiteBucketArn`,
    });

    new cdk.CfnOutput(this, 'WebsiteUrl', {
      value: this.bucketWebsiteUrl,
      description: 'Frontend website URL (HTTP)',
      exportName: `${env}-WebsiteUrl`,
    });

    // Tag resources
    cdk.Tags.of(this).add('Environment', env);
    cdk.Tags.of(this).add('Service', 'Echoes-Frontend');
  }
}