import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as route53 from 'aws-cdk-lib/aws-route53';
import * as route53Targets from 'aws-cdk-lib/aws-route53-targets';
import * as acm from 'aws-cdk-lib/aws-certificatemanager';

export interface NetworkStackProps extends cdk.StackProps {
  frontendBucket: s3.Bucket;
  originAccessIdentity: cloudfront.OriginAccessIdentity;
  environment: string;
  domainName?: string; // Optional custom domain
}

export class EchoesNetworkStack extends cdk.Stack {
  public readonly distribution: cloudfront.Distribution;
  public readonly distributionUrl: string;

  constructor(scope: Construct, id: string, props: NetworkStackProps) {
    super(scope, id, props);

    const env = props.environment;

    // Use the OAI passed from Frontend stack
    const originAccessIdentity = props.originAccessIdentity;

    // CloudFront distribution configuration
    let distributionConfig: cloudfront.DistributionProps;

    // If custom domain is provided, set up certificate and domain
    if (props.domainName) {
      // Create hosted zone (if it doesn't exist)
      const hostedZone = route53.HostedZone.fromLookup(this, 'HostedZone', {
        domainName: props.domainName,
      });

      // Request certificate (DNS validation)
      const certificate = new acm.Certificate(this, 'Certificate', {
        domainName: props.domainName,
        subjectAlternativeNames: [`*.${props.domainName}`],
        validation: acm.CertificateValidation.fromDns(hostedZone),
      });

      // Build distribution config with certificate and domain names
      distributionConfig = {
        defaultBehavior: {
          origin: new origins.S3Origin(props.frontendBucket, {
            originAccessIdentity
          }),
          viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
          allowedMethods: cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
          cachedMethods: cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
          compress: true,
          cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
        },
        defaultRootObject: 'index.html',
        errorResponses: [
          {
            httpStatus: 404,
            responseHttpStatus: 200,
            responsePagePath: '/index.html',
            ttl: cdk.Duration.minutes(5),
          },
          {
            httpStatus: 403,
            responseHttpStatus: 200,
            responsePagePath: '/index.html',
            ttl: cdk.Duration.minutes(5),
          }
        ],
        priceClass: cloudfront.PriceClass.PRICE_CLASS_100,
        comment: `Echoes ${env} Frontend Distribution`,
        enabled: true,
        certificate: certificate,
        domainNames: [
          props.domainName,
          `www.${props.domainName}`,
          `app.${props.domainName}`,
        ],
      };
    } else {
      // Build distribution config without certificate and domain names
      distributionConfig = {
        defaultBehavior: {
          origin: new origins.S3Origin(props.frontendBucket, {
            originAccessIdentity
          }),
          viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
          allowedMethods: cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
          cachedMethods: cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
          compress: true,
          cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
        },
        defaultRootObject: 'index.html',
        errorResponses: [
          {
            httpStatus: 404,
            responseHttpStatus: 200,
            responsePagePath: '/index.html',
            ttl: cdk.Duration.minutes(5),
          },
          {
            httpStatus: 403,
            responseHttpStatus: 200,
            responsePagePath: '/index.html',
            ttl: cdk.Duration.minutes(5),
          }
        ],
        priceClass: cloudfront.PriceClass.PRICE_CLASS_100,
        comment: `Echoes ${env} Frontend Distribution`,
        enabled: true,
      };
    }

    // Create CloudFront distribution
    this.distribution = new cloudfront.Distribution(this, 'Distribution', distributionConfig);

    // Store the distribution URL
    this.distributionUrl = `https://${this.distribution.distributionDomainName}`;

    // Create Route 53 records if custom domain is provided
    if (props.domainName) {
      const hostedZone = route53.HostedZone.fromLookup(this, 'HostedZoneLookup', {
        domainName: props.domainName,
      });

      // Create A record for root domain
      new route53.ARecord(this, 'AliasRecord', {
        zone: hostedZone,
        recordName: props.domainName,
        target: route53.RecordTarget.fromAlias(
          new route53Targets.CloudFrontTarget(this.distribution)
        ),
      });

      // Create A record for www subdomain
      new route53.ARecord(this, 'WwwAliasRecord', {
        zone: hostedZone,
        recordName: `www.${props.domainName}`,
        target: route53.RecordTarget.fromAlias(
          new route53Targets.CloudFrontTarget(this.distribution)
        ),
      });

      // Create A record for app subdomain
      new route53.ARecord(this, 'AppAliasRecord', {
        zone: hostedZone,
        recordName: `app.${props.domainName}`,
        target: route53.RecordTarget.fromAlias(
          new route53Targets.CloudFrontTarget(this.distribution)
        ),
      });
    }

    // Outputs
    new cdk.CfnOutput(this, 'DistributionId', {
      value: this.distribution.distributionId,
      description: 'CloudFront Distribution ID',
      exportName: `${env}-CloudFrontDistributionId`,
    });

    new cdk.CfnOutput(this, 'DistributionDomainName', {
      value: this.distribution.distributionDomainName,
      description: 'CloudFront Distribution Domain Name',
      exportName: `${env}-CloudFrontDomainName`,
    });

    new cdk.CfnOutput(this, 'FrontendUrl', {
      value: this.distributionUrl,
      description: 'Frontend URL (HTTPS)',
      exportName: `${env}-FrontendUrl`,
    });

    if (props.domainName) {
      new cdk.CfnOutput(this, 'CustomDomainUrl', {
        value: `https://${props.domainName}`,
        description: 'Custom Domain URL',
        exportName: `${env}-CustomDomainUrl`,
      });
    }

    // Tag resources
    cdk.Tags.of(this).add('Environment', env);
    cdk.Tags.of(this).add('Service', 'Echoes-Network');
  }
}