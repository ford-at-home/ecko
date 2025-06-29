"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.EchoesNetworkStack = void 0;
const cdk = require("aws-cdk-lib");
const cloudfront = require("aws-cdk-lib/aws-cloudfront");
const origins = require("aws-cdk-lib/aws-cloudfront-origins");
const route53 = require("aws-cdk-lib/aws-route53");
const route53Targets = require("aws-cdk-lib/aws-route53-targets");
const acm = require("aws-cdk-lib/aws-certificatemanager");
class EchoesNetworkStack extends cdk.Stack {
    constructor(scope, id, props) {
        super(scope, id, props);
        const env = props.environment;
        // Use the OAI passed from Frontend stack
        const originAccessIdentity = props.originAccessIdentity;
        // CloudFront distribution configuration
        let distributionConfig;
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
        }
        else {
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
                target: route53.RecordTarget.fromAlias(new route53Targets.CloudFrontTarget(this.distribution)),
            });
            // Create A record for www subdomain
            new route53.ARecord(this, 'WwwAliasRecord', {
                zone: hostedZone,
                recordName: `www.${props.domainName}`,
                target: route53.RecordTarget.fromAlias(new route53Targets.CloudFrontTarget(this.distribution)),
            });
            // Create A record for app subdomain
            new route53.ARecord(this, 'AppAliasRecord', {
                zone: hostedZone,
                recordName: `app.${props.domainName}`,
                target: route53.RecordTarget.fromAlias(new route53Targets.CloudFrontTarget(this.distribution)),
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
exports.EchoesNetworkStack = EchoesNetworkStack;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibmV0d29yay1zdGFjay5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbIm5ldHdvcmstc3RhY2sudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7O0FBQUEsbUNBQW1DO0FBRW5DLHlEQUF5RDtBQUN6RCw4REFBOEQ7QUFFOUQsbURBQW1EO0FBQ25ELGtFQUFrRTtBQUNsRSwwREFBMEQ7QUFTMUQsTUFBYSxrQkFBbUIsU0FBUSxHQUFHLENBQUMsS0FBSztJQUkvQyxZQUFZLEtBQWdCLEVBQUUsRUFBVSxFQUFFLEtBQXdCO1FBQ2hFLEtBQUssQ0FBQyxLQUFLLEVBQUUsRUFBRSxFQUFFLEtBQUssQ0FBQyxDQUFDO1FBRXhCLE1BQU0sR0FBRyxHQUFHLEtBQUssQ0FBQyxXQUFXLENBQUM7UUFFOUIseUNBQXlDO1FBQ3pDLE1BQU0sb0JBQW9CLEdBQUcsS0FBSyxDQUFDLG9CQUFvQixDQUFDO1FBRXhELHdDQUF3QztRQUN4QyxJQUFJLGtCQUFnRCxDQUFDO1FBRXJELDhEQUE4RDtRQUM5RCxJQUFJLEtBQUssQ0FBQyxVQUFVLEVBQUU7WUFDcEIsMkNBQTJDO1lBQzNDLE1BQU0sVUFBVSxHQUFHLE9BQU8sQ0FBQyxVQUFVLENBQUMsVUFBVSxDQUFDLElBQUksRUFBRSxZQUFZLEVBQUU7Z0JBQ25FLFVBQVUsRUFBRSxLQUFLLENBQUMsVUFBVTthQUM3QixDQUFDLENBQUM7WUFFSCx1Q0FBdUM7WUFDdkMsTUFBTSxXQUFXLEdBQUcsSUFBSSxHQUFHLENBQUMsV0FBVyxDQUFDLElBQUksRUFBRSxhQUFhLEVBQUU7Z0JBQzNELFVBQVUsRUFBRSxLQUFLLENBQUMsVUFBVTtnQkFDNUIsdUJBQXVCLEVBQUUsQ0FBQyxLQUFLLEtBQUssQ0FBQyxVQUFVLEVBQUUsQ0FBQztnQkFDbEQsVUFBVSxFQUFFLEdBQUcsQ0FBQyxxQkFBcUIsQ0FBQyxPQUFPLENBQUMsVUFBVSxDQUFDO2FBQzFELENBQUMsQ0FBQztZQUVILDhEQUE4RDtZQUM5RCxrQkFBa0IsR0FBRztnQkFD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QUMsQ0FBQztJQUNyRCxDQUFDO0NBQ0Y7QUEzS0QsZ0RBMktDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0ICogYXMgY2RrIGZyb20gJ2F3cy1jZGstbGliJztcbmltcG9ydCB7IENvbnN0cnVjdCB9IGZyb20gJ2NvbnN0cnVjdHMnO1xuaW1wb3J0ICogYXMgY2xvdWRmcm9udCBmcm9tICdhd3MtY2RrLWxpYi9hd3MtY2xvdWRmcm9udCc7XG5pbXBvcnQgKiBhcyBvcmlnaW5zIGZyb20gJ2F3cy1jZGstbGliL2F3cy1jbG91ZGZyb250LW9yaWdpbnMnO1xuaW1wb3J0ICogYXMgczMgZnJvbSAnYXdzLWNkay1saWIvYXdzLXMzJztcbmltcG9ydCAqIGFzIHJvdXRlNTMgZnJvbSAnYXdzLWNkay1saWIvYXdzLXJvdXRlNTMnO1xuaW1wb3J0ICogYXMgcm91dGU1M1RhcmdldHMgZnJvbSAnYXdzLWNkay1saWIvYXdzLXJvdXRlNTMtdGFyZ2V0cyc7XG5pbXBvcnQgKiBhcyBhY20gZnJvbSAnYXdzLWNkay1saWIvYXdzLWNlcnRpZmljYXRlbWFuYWdlcic7XG5cbmV4cG9ydCBpbnRlcmZhY2UgTmV0d29ya1N0YWNrUHJvcHMgZXh0ZW5kcyBjZGsuU3RhY2tQcm9wcyB7XG4gIGZyb250ZW5kQnVja2V0OiBzMy5CdWNrZXQ7XG4gIG9yaWdpbkFjY2Vzc0lkZW50aXR5OiBjbG91ZGZyb250Lk9yaWdpbkFjY2Vzc0lkZW50aXR5O1xuICBlbnZpcm9ubWVudDogc3RyaW5nO1xuICBkb21haW5OYW1lPzogc3RyaW5nOyAvLyBPcHRpb25hbCBjdXN0b20gZG9tYWluXG59XG5cbmV4cG9ydCBjbGFzcyBFY2hvZXNOZXR3b3JrU3RhY2sgZXh0ZW5kcyBjZGsuU3RhY2sge1xuICBwdWJsaWMgcmVhZG9ubHkgZGlzdHJpYnV0aW9uOiBjbG91ZGZyb250LkRpc3RyaWJ1dGlvbjtcbiAgcHVibGljIHJlYWRvbmx5IGRpc3RyaWJ1dGlvblVybDogc3RyaW5nO1xuXG4gIGNvbnN0cnVjdG9yKHNjb3BlOiBDb25zdHJ1Y3QsIGlkOiBzdHJpbmcsIHByb3BzOiBOZXR3b3JrU3RhY2tQcm9wcykge1xuICAgIHN1cGVyKHNjb3BlLCBpZCwgcHJvcHMpO1xuXG4gICAgY29uc3QgZW52ID0gcHJvcHMuZW52aXJvbm1lbnQ7XG5cbiAgICAvLyBVc2UgdGhlIE9BSSBwYXNzZWQgZnJvbSBGcm9udGVuZCBzdGFja1xuICAgIGNvbnN0IG9yaWdpbkFjY2Vzc0lkZW50aXR5ID0gcHJvcHMub3JpZ2luQWNjZXNzSWRlbnRpdHk7XG5cbiAgICAvLyBDbG91ZEZyb250IGRpc3RyaWJ1dGlvbiBjb25maWd1cmF0aW9uXG4gICAgbGV0IGRpc3RyaWJ1dGlvbkNvbmZpZzogY2xvdWRmcm9udC5EaXN0cmlidXRpb25Qcm9wcztcblxuICAgIC8vIElmIGN1c3RvbSBkb21haW4gaXMgcHJvdmlkZWQsIHNldCB1cCBjZXJ0aWZpY2F0ZSBhbmQgZG9tYWluXG4gICAgaWYgKHByb3BzLmRvbWFpbk5hbWUpIHtcbiAgICAgIC8vIENyZWF0ZSBob3N0ZWQgem9uZSAoaWYgaXQgZG9lc24ndCBleGlzdClcbiAgICAgIGNvbnN0IGhvc3RlZFpvbmUgPSByb3V0ZTUzLkhvc3RlZFpvbmUuZnJvbUxvb2t1cCh0aGlzLCAnSG9zdGVkWm9uZScsIHtcbiAgICAgICAgZG9tYWluTmFtZTogcHJvcHMuZG9tYWluTmFtZSxcbiAgICAgIH0pO1xuXG4gICAgICAvLyBSZXF1ZXN0IGNlcnRpZmljYXRlIChETlMgdmFsaWRhdGlvbilcbiAgICAgIGNvbnN0IGNlcnRpZmljYXRlID0gbmV3IGFjbS5DZXJ0aWZpY2F0ZSh0aGlzLCAnQ2VydGlmaWNhdGUnLCB7XG4gICAgICAgIGRvbWFpbk5hbWU6IHByb3BzLmRvbWFpbk5hbWUsXG4gICAgICAgIHN1YmplY3RBbHRlcm5hdGl2ZU5hbWVzOiBbYCouJHtwcm9wcy5kb21haW5OYW1lfWBdLFxuICAgICAgICB2YWxpZGF0aW9uOiBhY20uQ2VydGlmaWNhdGVWYWxpZGF0aW9uLmZyb21EbnMoaG9zdGVkWm9uZSksXG4gICAgICB9KTtcblxuICAgICAgLy8gQnVpbGQgZGlzdHJpYnV0aW9uIGNvbmZpZyB3aXRoIGNlcnRpZmljYXRlIGFuZCBkb21haW4gbmFtZXNcbiAgICAgIGRpc3RyaWJ1dGlvbkNvbmZpZyA9IHtcbiAgICAgICAgZGVmYXVsdEJlaGF2aW9yOiB7XG4gICAgICAgICAgb3JpZ2luOiBuZXcgb3JpZ2lucy5TM09yaWdpbihwcm9wcy5mcm9udGVuZEJ1Y2tldCwge1xuICAgICAgICAgICAgb3JpZ2luQWNjZXNzSWRlbnRpdHlcbiAgICAgICAgICB9KSxcbiAgICAgICAgICB2aWV3ZXJQcm90b2NvbFBvbGljeTogY2xvdWRmcm9udC5WaWV3ZXJQcm90b2NvbFBvbGljeS5SRURJUkVDVF9UT19IVFRQUyxcbiAgICAgICAgICBhbGxvd2VkTWV0aG9kczogY2xvdWRmcm9udC5BbGxvd2VkTWV0aG9kcy5BTExPV19HRVRfSEVBRF9PUFRJT05TLFxuICAgICAgICAgIGNhY2hlZE1ldGhvZHM6IGNsb3VkZnJvbnQuQ2FjaGVkTWV0aG9kcy5DQUNIRV9HRVRfSEVBRF9PUFRJT05TLFxuICAgICAgICAgIGNvbXByZXNzOiB0cnVlLFxuICAgICAgICAgIGNhY2hlUG9saWN5OiBjbG91ZGZyb250LkNhY2hlUG9saWN5LkNBQ0hJTkdfT1BUSU1JWkVELFxuICAgICAgICB9LFxuICAgICAgICBkZWZhdWx0Um9vdE9iamVjdDogJ2luZGV4Lmh0bWwnLFxuICAgICAgICBlcnJvclJlc3BvbnNlczogW1xuICAgICAgICAgIHtcbiAgICAgICAgICAgIGh0dHBTdGF0dXM6IDQwNCxcbiAgICAgICAgICAgIHJlc3BvbnNlSHR0cFN0YXR1czogMjAwLFxuICAgICAgICAgICAgcmVzcG9uc2VQYWdlUGF0aDogJy9pbmRleC5odG1sJyxcbiAgICAgICAgICAgIHR0bDogY2RrLkR1cmF0aW9uLm1pbnV0ZXMoNSksXG4gICAgICAgICAgfSxcbiAgICAgICAgICB7XG4gICAgICAgICAgICBodHRwU3RhdHVzOiA0MDMsXG4gICAgICAgICAgICByZXNwb25zZUh0dHBTdGF0dXM6IDIwMCxcbiAgICAgICAgICAgIHJlc3BvbnNlUGFnZVBhdGg6ICcvaW5kZXguaHRtbCcsXG4gICAgICAgICAgICB0dGw6IGNkay5EdXJhdGlvbi5taW51dGVzKDUpLFxuICAgICAgICAgIH1cbiAgICAgICAgXSxcbiAgICAgICAgcHJpY2VDbGFzczogY2xvdWRmcm9udC5QcmljZUNsYXNzLlBSSUNFX0NMQVNTXzEwMCxcbiAgICAgICAgY29tbWVudDogYEVjaG9lcyAke2Vudn0gRnJvbnRlbmQgRGlzdHJpYnV0aW9uYCxcbiAgICAgICAgZW5hYmxlZDogdHJ1ZSxcbiAgICAgICAgY2VydGlmaWNhdGU6IGNlcnRpZmljYXRlLFxuICAgICAgICBkb21haW5OYW1lczogW1xuICAgICAgICAgIHByb3BzLmRvbWFpbk5hbWUsXG4gICAgICAgICAgYHd3dy4ke3Byb3BzLmRvbWFpbk5hbWV9YCxcbiAgICAgICAgICBgYXBwLiR7cHJvcHMuZG9tYWluTmFtZX1gLFxuICAgICAgICBdLFxuICAgICAgfTtcbiAgICB9IGVsc2Uge1xuICAgICAgLy8gQnVpbGQgZGlzdHJpYnV0aW9uIGNvbmZpZyB3aXRob3V0IGNlcnRpZmljYXRlIGFuZCBkb21haW4gbmFtZXNcbiAgICAgIGRpc3RyaWJ1dGlvbkNvbmZpZyA9IHtcbiAgICAgICAgZGVmYXVsdEJlaGF2aW9yOiB7XG4gICAgICAgICAgb3JpZ2luOiBuZXcgb3JpZ2lucy5TM09yaWdpbihwcm9wcy5mcm9udGVuZEJ1Y2tldCwge1xuICAgICAgICAgICAgb3JpZ2luQWNjZXNzSWRlbnRpdHlcbiAgICAgICAgICB9KSxcbiAgICAgICAgICB2aWV3ZXJQcm90b2NvbFBvbGljeTogY2xvdWRmcm9udC5WaWV3ZXJQcm90b2NvbFBvbGljeS5SRURJUkVDVF9UT19IVFRQUyxcbiAgICAgICAgICBhbGxvd2VkTWV0aG9kczogY2xvdWRmcm9udC5BbGxvd2VkTWV0aG9kcy5BTExPV19HRVRfSEVBRF9PUFRJT05TLFxuICAgICAgICAgIGNhY2hlZE1ldGhvZHM6IGNsb3VkZnJvbnQuQ2FjaGVkTWV0aG9kcy5DQUNIRV9HRVRfSEVBRF9PUFRJT05TLFxuICAgICAgICAgIGNvbXByZXNzOiB0cnVlLFxuICAgICAgICAgIGNhY2hlUG9saWN5OiBjbG91ZGZyb250LkNhY2hlUG9saWN5LkNBQ0hJTkdfT1BUSU1JWkVELFxuICAgICAgICB9LFxuICAgICAgICBkZWZhdWx0Um9vdE9iamVjdDogJ2luZGV4Lmh0bWwnLFxuICAgICAgICBlcnJvclJlc3BvbnNlczogW1xuICAgICAgICAgIHtcbiAgICAgICAgICAgIGh0dHBTdGF0dXM6IDQwNCxcbiAgICAgICAgICAgIHJlc3BvbnNlSHR0cFN0YXR1czogMjAwLFxuICAgICAgICAgICAgcmVzcG9uc2VQYWdlUGF0aDogJy9pbmRleC5odG1sJyxcbiAgICAgICAgICAgIHR0bDogY2RrLkR1cmF0aW9uLm1pbnV0ZXMoNSksXG4gICAgICAgICAgfSxcbiAgICAgICAgICB7XG4gICAgICAgICAgICBodHRwU3RhdHVzOiA0MDMsXG4gICAgICAgICAgICByZXNwb25zZUh0dHBTdGF0dXM6IDIwMCxcbiAgICAgICAgICAgIHJlc3BvbnNlUGFnZVBhdGg6ICcvaW5kZXguaHRtbCcsXG4gICAgICAgICAgICB0dGw6IGNkay5EdXJhdGlvbi5taW51dGVzKDUpLFxuICAgICAgICAgIH1cbiAgICAgICAgXSxcbiAgICAgICAgcHJpY2VDbGFzczogY2xvdWRmcm9udC5QcmljZUNsYXNzLlBSSUNFX0NMQVNTXzEwMCxcbiAgICAgICAgY29tbWVudDogYEVjaG9lcyAke2Vudn0gRnJvbnRlbmQgRGlzdHJpYnV0aW9uYCxcbiAgICAgICAgZW5hYmxlZDogdHJ1ZSxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgLy8gQ3JlYXRlIENsb3VkRnJvbnQgZGlzdHJpYnV0aW9uXG4gICAgdGhpcy5kaXN0cmlidXRpb24gPSBuZXcgY2xvdWRmcm9udC5EaXN0cmlidXRpb24odGhpcywgJ0Rpc3RyaWJ1dGlvbicsIGRpc3RyaWJ1dGlvbkNvbmZpZyk7XG5cbiAgICAvLyBTdG9yZSB0aGUgZGlzdHJpYnV0aW9uIFVSTFxuICAgIHRoaXMuZGlzdHJpYnV0aW9uVXJsID0gYGh0dHBzOi8vJHt0aGlzLmRpc3RyaWJ1dGlvbi5kaXN0cmlidXRpb25Eb21haW5OYW1lfWA7XG5cbiAgICAvLyBDcmVhdGUgUm91dGUgNTMgcmVjb3JkcyBpZiBjdXN0b20gZG9tYWluIGlzIHByb3ZpZGVkXG4gICAgaWYgKHByb3BzLmRvbWFpbk5hbWUpIHtcbiAgICAgIGNvbnN0IGhvc3RlZFpvbmUgPSByb3V0ZTUzLkhvc3RlZFpvbmUuZnJvbUxvb2t1cCh0aGlzLCAnSG9zdGVkWm9uZUxvb2t1cCcsIHtcbiAgICAgICAgZG9tYWluTmFtZTogcHJvcHMuZG9tYWluTmFtZSxcbiAgICAgIH0pO1xuXG4gICAgICAvLyBDcmVhdGUgQSByZWNvcmQgZm9yIHJvb3QgZG9tYWluXG4gICAgICBuZXcgcm91dGU1My5BUmVjb3JkKHRoaXMsICdBbGlhc1JlY29yZCcsIHtcbiAgICAgICAgem9uZTogaG9zdGVkWm9uZSxcbiAgICAgICAgcmVjb3JkTmFtZTogcHJvcHMuZG9tYWluTmFtZSxcbiAgICAgICAgdGFyZ2V0OiByb3V0ZTUzLlJlY29yZFRhcmdldC5mcm9tQWxpYXMoXG4gICAgICAgICAgbmV3IHJvdXRlNTNUYXJnZXRzLkNsb3VkRnJvbnRUYXJnZXQodGhpcy5kaXN0cmlidXRpb24pXG4gICAgICAgICksXG4gICAgICB9KTtcblxuICAgICAgLy8gQ3JlYXRlIEEgcmVjb3JkIGZvciB3d3cgc3ViZG9tYWluXG4gICAgICBuZXcgcm91dGU1My5BUmVjb3JkKHRoaXMsICdXd3dBbGlhc1JlY29yZCcsIHtcbiAgICAgICAgem9uZTogaG9zdGVkWm9uZSxcbiAgICAgICAgcmVjb3JkTmFtZTogYHd3dy4ke3Byb3BzLmRvbWFpbk5hbWV9YCxcbiAgICAgICAgdGFyZ2V0OiByb3V0ZTUzLlJlY29yZFRhcmdldC5mcm9tQWxpYXMoXG4gICAgICAgICAgbmV3IHJvdXRlNTNUYXJnZXRzLkNsb3VkRnJvbnRUYXJnZXQodGhpcy5kaXN0cmlidXRpb24pXG4gICAgICAgICksXG4gICAgICB9KTtcblxuICAgICAgLy8gQ3JlYXRlIEEgcmVjb3JkIGZvciBhcHAgc3ViZG9tYWluXG4gICAgICBuZXcgcm91dGU1My5BUmVjb3JkKHRoaXMsICdBcHBBbGlhc1JlY29yZCcsIHtcbiAgICAgICAgem9uZTogaG9zdGVkWm9uZSxcbiAgICAgICAgcmVjb3JkTmFtZTogYGFwcC4ke3Byb3BzLmRvbWFpbk5hbWV9YCxcbiAgICAgICAgdGFyZ2V0OiByb3V0ZTUzLlJlY29yZFRhcmdldC5mcm9tQWxpYXMoXG4gICAgICAgICAgbmV3IHJvdXRlNTNUYXJnZXRzLkNsb3VkRnJvbnRUYXJnZXQodGhpcy5kaXN0cmlidXRpb24pXG4gICAgICAgICksXG4gICAgICB9KTtcbiAgICB9XG5cbiAgICAvLyBPdXRwdXRzXG4gICAgbmV3IGNkay5DZm5PdXRwdXQodGhpcywgJ0Rpc3RyaWJ1dGlvbklkJywge1xuICAgICAgdmFsdWU6IHRoaXMuZGlzdHJpYnV0aW9uLmRpc3RyaWJ1dGlvbklkLFxuICAgICAgZGVzY3JpcHRpb246ICdDbG91ZEZyb250IERpc3RyaWJ1dGlvbiBJRCcsXG4gICAgICBleHBvcnROYW1lOiBgJHtlbnZ9LUNsb3VkRnJvbnREaXN0cmlidXRpb25JZGAsXG4gICAgfSk7XG5cbiAgICBuZXcgY2RrLkNmbk91dHB1dCh0aGlzLCAnRGlzdHJpYnV0aW9uRG9tYWluTmFtZScsIHtcbiAgICAgIHZhbHVlOiB0aGlzLmRpc3RyaWJ1dGlvbi5kaXN0cmlidXRpb25Eb21haW5OYW1lLFxuICAgICAgZGVzY3JpcHRpb246ICdDbG91ZEZyb250IERpc3RyaWJ1dGlvbiBEb21haW4gTmFtZScsXG4gICAgICBleHBvcnROYW1lOiBgJHtlbnZ9LUNsb3VkRnJvbnREb21haW5OYW1lYCxcbiAgICB9KTtcblxuICAgIG5ldyBjZGsuQ2ZuT3V0cHV0KHRoaXMsICdGcm9udGVuZFVybCcsIHtcbiAgICAgIHZhbHVlOiB0aGlzLmRpc3RyaWJ1dGlvblVybCxcbiAgICAgIGRlc2NyaXB0aW9uOiAnRnJvbnRlbmQgVVJMIChIVFRQUyknLFxuICAgICAgZXhwb3J0TmFtZTogYCR7ZW52fS1Gcm9udGVuZFVybGAsXG4gICAgfSk7XG5cbiAgICBpZiAocHJvcHMuZG9tYWluTmFtZSkge1xuICAgICAgbmV3IGNkay5DZm5PdXRwdXQodGhpcywgJ0N1c3RvbURvbWFpblVybCcsIHtcbiAgICAgICAgdmFsdWU6IGBodHRwczovLyR7cHJvcHMuZG9tYWluTmFtZX1gLFxuICAgICAgICBkZXNjcmlwdGlvbjogJ0N1c3RvbSBEb21haW4gVVJMJyxcbiAgICAgICAgZXhwb3J0TmFtZTogYCR7ZW52fS1DdXN0b21Eb21haW5VcmxgLFxuICAgICAgfSk7XG4gICAgfVxuXG4gICAgLy8gVGFnIHJlc291cmNlc1xuICAgIGNkay5UYWdzLm9mKHRoaXMpLmFkZCgnRW52aXJvbm1lbnQnLCBlbnYpO1xuICAgIGNkay5UYWdzLm9mKHRoaXMpLmFkZCgnU2VydmljZScsICdFY2hvZXMtTmV0d29yaycpO1xuICB9XG59Il19