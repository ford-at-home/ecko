"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.EchoesFrontendStack = void 0;
const cdk = require("aws-cdk-lib");
const s3 = require("aws-cdk-lib/aws-s3");
const s3deploy = require("aws-cdk-lib/aws-s3-deployment");
const cloudfront = require("aws-cdk-lib/aws-cloudfront");
const path = require("path");
class EchoesFrontendStack extends cdk.Stack {
    constructor(scope, id, props) {
        super(scope, id, props);
        const env = props.environment;
        // Create S3 bucket for frontend hosting
        this.websiteBucket = new s3.Bucket(this, 'WebsiteBucket', {
            bucketName: `echoes-frontend-${env}-${this.account}`,
            websiteIndexDocument: 'index.html',
            websiteErrorDocument: 'index.html',
            publicReadAccess: false,
            blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
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
                prune: true,
                retainOnDelete: false,
            });
        }
        catch (error) {
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
exports.EchoesFrontendStack = EchoesFrontendStack;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZnJvbnRlbmQtc3RhY2suanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJmcm9udGVuZC1zdGFjay50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7QUFBQSxtQ0FBbUM7QUFFbkMseUNBQXlDO0FBQ3pDLDBEQUEwRDtBQUUxRCx5REFBeUQ7QUFDekQsNkJBQTZCO0FBTTdCLE1BQWEsbUJBQW9CLFNBQVEsR0FBRyxDQUFDLEtBQUs7SUFLaEQsWUFBWSxLQUFnQixFQUFFLEVBQVUsRUFBRSxLQUF5QjtRQUNqRSxLQUFLLENBQUMsS0FBSyxFQUFFLEVBQUUsRUFBRSxLQUFLLENBQUMsQ0FBQztRQUV4QixNQUFNLEdBQUcsR0FBRyxLQUFLLENBQUMsV0FBVyxDQUFDO1FBRTlCLHdDQUF3QztRQUN4QyxJQUFJLENBQUMsYUFBYSxHQUFHLElBQUksRUFBRSxDQUFDLE1BQU0sQ0FBQyxJQUFJLEVBQUUsZUFBZSxFQUFFO1lBQ3hELFVBQVUsRUFBRSxtQkFBbUIsR0FBRyxJQUFJLElBQUksQ0FBQyxPQUFPLEVBQUU7WUFDcEQsb0JBQW9CLEVBQUUsWUFBWTtZQUNsQyxvQkFBb0IsRUFBRSxZQUFZO1lBQ2xDLGdCQUFnQixFQUFFLEtBQUs7WUFDdkIsaUJBQWlCLEVBQUUsRUFBRSxDQUFDLGlCQUFpQixDQUFDLFNBQVM7WUFDakQsSUFBSSxFQUFFO2dCQUNKO29CQUNFLGNBQWMsRUFBRTt3QkFDZCxFQUFFLENBQUMsV0FBVyxDQUFDLEdBQUc7d0JBQ2xCLEVBQUUsQ0FBQyxXQUFXLENBQUMsSUFBSTtxQkFDcEI7b0JBQ0QsY0FBYyxFQUFFLENBQUMsR0FBRyxDQUFDO29CQUNyQixjQUFjLEVBQUUsQ0FBQyxHQUFHLENBQUM7b0JBQ3JCLE1BQU0sRUFBRSxJQUFJO2lCQUNiO2FBQ0Y7WUFDRCxhQUFhLEVBQUUsR0FBRyxLQUFLLE1BQU07Z0JBQzNCLENBQUMsQ0FBQyxHQUFHLENBQUMsYUFBYSxDQUFDLE1BQU07Z0JBQzFCLENBQUMsQ0FBQyxHQUFHLENBQUMsYUFBYSxDQUFDLE9BQU87WUFDN0IsaUJBQWlCLEVBQUUsR0FBRyxLQUFLLE1BQU0sRUFBRSwrQkFBK0I7U0FDbkUsQ0FBQyxDQUFDO1FBRUgsMkNBQTJDO1FBQzNDLElBQUksQ0FBQyxvQkFBb0IsR0FBRyxJQUFJLFVBQVUsQ0FBQyxvQkFBb0IsQ0FBQyxJQUFJLEVBQUUsS0FBSyxFQUFFO1lBQzNFLE9BQU8sRUFBRSxrQkFBa0IsR0FBRyxXQUFXO1NBQzFDLENBQUMsQ0FBQztRQUVILDRDQUE0QztRQUM1QyxJQUFJLENBQUMsYUFBYSxDQUFDLFNBQVMsQ0FBQyxJQUFJLENBQUMsb0JBQW9CLENBQUMsQ0FBQztRQUV4RCw0Q0FBNEM7UUFDNUMsTUFBTSxpQkFBaUIsR0FBRyxJQUFJLENBQUMsSUFBSSxDQUFDLFNBQVMsRUFBRSxJQUFJLEVBQUUsSUFBSSxFQUFFLElBQUksRUFBRSxVQUFVLEVBQUUsTUFBTSxDQUFDLENBQUM7UUFFckYsd0NBQXdDO1FBQ3hDLElBQUk7WUFDRixJQUFJLFFBQVEsQ0FBQyxnQkFBZ0IsQ0FBQyxJQUFJLEVBQUUsZUFBZSxFQUFFO2dCQUNuRCxPQUFPLEVBQUUsQ0FBQyxRQUFRLENBQUMsTUFBTSxDQUFDLEtBQUssQ0FBQyxpQkFBaUIsQ0FBQyxDQUFDO2dCQUNuRCxpQkFBaUIsRUFBRSxJQUFJLENBQUMsYUFBYTtnQkFDckMsS0FBSyxFQUFFLElBQUk7Z0JBQ1gsY0FBYyxFQUFFLEtBQUs7YUFDdEIsQ0FBQyxDQUFDO1NBQ0o7UUFBQyxPQUFPLEtBQUssRUFBRTtZQUNkLE9BQU8sQ0FBQyxHQUFHLENBQUMsMERBQTBELENBQUMsQ0FBQztZQUN4RSxPQUFPLENBQUMsR0FBRyxDQUFDLGlFQUFpRSxDQUFDLENBQUM7U0FDaEY7UUFFRCx3QkFBd0I7UUFDeEIsSUFBSSxDQUFDLGdCQUFnQixHQUFHLElBQUksQ0FBQyxhQUFhLENBQUMsZ0JBQWdCLENBQUM7UUFFNUQsVUFBVTtRQUNWLElBQUksR0FBRyxDQUFDLFNBQVMsQ0FBQyxJQUFJLEVBQUUsbUJBQW1CLEVBQUU7WUFDM0MsS0FBSyxFQUFFLElBQUksQ0FBQyxhQUFhLENBQUMsVUFBVTtZQUNwQyxXQUFXLEVBQUUseUJBQXlCO1lBQ3RDLFVBQVUsRUFBRSxHQUFHLEdBQUcsb0JBQW9CO1NBQ3ZDLENBQUMsQ0FBQztRQUVILElBQUksR0FBRyxDQUFDLFNBQVMsQ0FBQyxJQUFJLEVBQUUsa0JBQWtCLEVBQUU7WUFDMUMsS0FBSyxFQUFFLElBQUksQ0FBQyxhQUFhLENBQUMsU0FBUztZQUNuQyxXQUFXLEVBQUUsd0JBQXdCO1lBQ3JDLFVBQVUsRUFBRSxHQUFHLEdBQUcsbUJBQW1CO1NBQ3RDLENBQUMsQ0FBQztRQUVILElBQUksR0FBRyxDQUFDLFNBQVMsQ0FBQyxJQUFJLEVBQUUsWUFBWSxFQUFFO1lBQ3BDLEtBQUssRUFBRSxJQUFJLENBQUMsZ0JBQWdCO1lBQzVCLFdBQVcsRUFBRSw2QkFBNkI7WUFDMUMsVUFBVSxFQUFFLEdBQUcsR0FBRyxhQUFhO1NBQ2hDLENBQUMsQ0FBQztRQUVILGdCQUFnQjtRQUNoQixHQUFHLENBQUMsSUFBSSxDQUFDLEVBQUUsQ0FBQyxJQUFJLENBQUMsQ0FBQyxHQUFHLENBQUMsYUFBYSxFQUFFLEdBQUcsQ0FBQyxDQUFDO1FBQzFDLEdBQUcsQ0FBQyxJQUFJLENBQUMsRUFBRSxDQUFDLElBQUksQ0FBQyxDQUFDLEdBQUcsQ0FBQyxTQUFTLEVBQUUsaUJBQWlCLENBQUMsQ0FBQztJQUN0RCxDQUFDO0NBQ0Y7QUFwRkQsa0RBb0ZDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0ICogYXMgY2RrIGZyb20gJ2F3cy1jZGstbGliJztcbmltcG9ydCB7IENvbnN0cnVjdCB9IGZyb20gJ2NvbnN0cnVjdHMnO1xuaW1wb3J0ICogYXMgczMgZnJvbSAnYXdzLWNkay1saWIvYXdzLXMzJztcbmltcG9ydCAqIGFzIHMzZGVwbG95IGZyb20gJ2F3cy1jZGstbGliL2F3cy1zMy1kZXBsb3ltZW50JztcbmltcG9ydCAqIGFzIGlhbSBmcm9tICdhd3MtY2RrLWxpYi9hd3MtaWFtJztcbmltcG9ydCAqIGFzIGNsb3VkZnJvbnQgZnJvbSAnYXdzLWNkay1saWIvYXdzLWNsb3VkZnJvbnQnO1xuaW1wb3J0ICogYXMgcGF0aCBmcm9tICdwYXRoJztcblxuZXhwb3J0IGludGVyZmFjZSBGcm9udGVuZFN0YWNrUHJvcHMgZXh0ZW5kcyBjZGsuU3RhY2tQcm9wcyB7XG4gIGVudmlyb25tZW50OiBzdHJpbmc7XG59XG5cbmV4cG9ydCBjbGFzcyBFY2hvZXNGcm9udGVuZFN0YWNrIGV4dGVuZHMgY2RrLlN0YWNrIHtcbiAgcHVibGljIHJlYWRvbmx5IHdlYnNpdGVCdWNrZXQ6IHMzLkJ1Y2tldDtcbiAgcHVibGljIHJlYWRvbmx5IGJ1Y2tldFdlYnNpdGVVcmw6IHN0cmluZztcbiAgcHVibGljIHJlYWRvbmx5IG9yaWdpbkFjY2Vzc0lkZW50aXR5OiBjbG91ZGZyb250Lk9yaWdpbkFjY2Vzc0lkZW50aXR5O1xuXG4gIGNvbnN0cnVjdG9yKHNjb3BlOiBDb25zdHJ1Y3QsIGlkOiBzdHJpbmcsIHByb3BzOiBGcm9udGVuZFN0YWNrUHJvcHMpIHtcbiAgICBzdXBlcihzY29wZSwgaWQsIHByb3BzKTtcblxuICAgIGNvbnN0IGVudiA9IHByb3BzLmVudmlyb25tZW50O1xuXG4gICAgLy8gQ3JlYXRlIFMzIGJ1Y2tldCBmb3IgZnJvbnRlbmQgaG9zdGluZ1xuICAgIHRoaXMud2Vic2l0ZUJ1Y2tldCA9IG5ldyBzMy5CdWNrZXQodGhpcywgJ1dlYnNpdGVCdWNrZXQnLCB7XG4gICAgICBidWNrZXROYW1lOiBgZWNob2VzLWZyb250ZW5kLSR7ZW52fS0ke3RoaXMuYWNjb3VudH1gLFxuICAgICAgd2Vic2l0ZUluZGV4RG9jdW1lbnQ6ICdpbmRleC5odG1sJyxcbiAgICAgIHdlYnNpdGVFcnJvckRvY3VtZW50OiAnaW5kZXguaHRtbCcsIC8vIEZvciBTUEEgcm91dGluZ1xuICAgICAgcHVibGljUmVhZEFjY2VzczogZmFsc2UsIC8vIENoYW5nZWQgdG8gZmFsc2Ugc2luY2Ugd2UncmUgdXNpbmcgQ2xvdWRGcm9udCBPQUlcbiAgICAgIGJsb2NrUHVibGljQWNjZXNzOiBzMy5CbG9ja1B1YmxpY0FjY2Vzcy5CTE9DS19BTEwsIC8vIEJsb2NrIGFsbCBwdWJsaWMgYWNjZXNzXG4gICAgICBjb3JzOiBbXG4gICAgICAgIHtcbiAgICAgICAgICBhbGxvd2VkTWV0aG9kczogW1xuICAgICAgICAgICAgczMuSHR0cE1ldGhvZHMuR0VULFxuICAgICAgICAgICAgczMuSHR0cE1ldGhvZHMuSEVBRCxcbiAgICAgICAgICBdLFxuICAgICAgICAgIGFsbG93ZWRPcmlnaW5zOiBbJyonXSxcbiAgICAgICAgICBhbGxvd2VkSGVhZGVyczogWycqJ10sXG4gICAgICAgICAgbWF4QWdlOiAzMDAwLFxuICAgICAgICB9LFxuICAgICAgXSxcbiAgICAgIHJlbW92YWxQb2xpY3k6IGVudiA9PT0gJ3Byb2QnIFxuICAgICAgICA/IGNkay5SZW1vdmFsUG9saWN5LlJFVEFJTiBcbiAgICAgICAgOiBjZGsuUmVtb3ZhbFBvbGljeS5ERVNUUk9ZLFxuICAgICAgYXV0b0RlbGV0ZU9iamVjdHM6IGVudiAhPT0gJ3Byb2QnLCAvLyBPbmx5IGF1dG8tZGVsZXRlIGluIG5vbi1wcm9kXG4gICAgfSk7XG5cbiAgICAvLyBDcmVhdGUgQ2xvdWRGcm9udCBPcmlnaW4gQWNjZXNzIElkZW50aXR5XG4gICAgdGhpcy5vcmlnaW5BY2Nlc3NJZGVudGl0eSA9IG5ldyBjbG91ZGZyb250Lk9yaWdpbkFjY2Vzc0lkZW50aXR5KHRoaXMsICdPQUknLCB7XG4gICAgICBjb21tZW50OiBgT0FJIGZvciBFY2hvZXMgJHtlbnZ9IGZyb250ZW5kYFxuICAgIH0pO1xuXG4gICAgLy8gR3JhbnQgQ2xvdWRGcm9udCBPQUkgYWNjZXNzIHRvIHRoZSBidWNrZXRcbiAgICB0aGlzLndlYnNpdGVCdWNrZXQuZ3JhbnRSZWFkKHRoaXMub3JpZ2luQWNjZXNzSWRlbnRpdHkpO1xuXG4gICAgLy8gRGVwbG95IGZyb250ZW5kIGJ1aWxkIGZpbGVzIGlmIHRoZXkgZXhpc3RcbiAgICBjb25zdCBmcm9udGVuZEJ1aWxkUGF0aCA9IHBhdGguam9pbihfX2Rpcm5hbWUsICcuLicsICcuLicsICcuLicsICdmcm9udGVuZCcsICdkaXN0Jyk7XG4gICAgXG4gICAgLy8gT25seSBkZXBsb3kgaWYgYnVpbGQgZGlyZWN0b3J5IGV4aXN0c1xuICAgIHRyeSB7XG4gICAgICBuZXcgczNkZXBsb3kuQnVja2V0RGVwbG95bWVudCh0aGlzLCAnRGVwbG95V2Vic2l0ZScsIHtcbiAgICAgICAgc291cmNlczogW3MzZGVwbG95LlNvdXJjZS5hc3NldChmcm9udGVuZEJ1aWxkUGF0aCldLFxuICAgICAgICBkZXN0aW5hdGlvbkJ1Y2tldDogdGhpcy53ZWJzaXRlQnVja2V0LFxuICAgICAgICBwcnVuZTogdHJ1ZSwgLy8gUmVtb3ZlIG9sZCBmaWxlc1xuICAgICAgICByZXRhaW5PbkRlbGV0ZTogZmFsc2UsXG4gICAgICB9KTtcbiAgICB9IGNhdGNoIChlcnJvcikge1xuICAgICAgY29uc29sZS5sb2coJ0Zyb250ZW5kIGJ1aWxkIGRpcmVjdG9yeSBub3QgZm91bmQuIFNraXBwaW5nIGRlcGxveW1lbnQuJyk7XG4gICAgICBjb25zb2xlLmxvZygnUnVuIFwibnBtIHJ1biBidWlsZFwiIGluIHRoZSBmcm9udGVuZCBkaXJlY3RvcnkgYmVmb3JlIGRlcGxveWluZy4nKTtcbiAgICB9XG5cbiAgICAvLyBTdG9yZSB0aGUgd2Vic2l0ZSBVUkxcbiAgICB0aGlzLmJ1Y2tldFdlYnNpdGVVcmwgPSB0aGlzLndlYnNpdGVCdWNrZXQuYnVja2V0V2Vic2l0ZVVybDtcblxuICAgIC8vIE91dHB1dHNcbiAgICBuZXcgY2RrLkNmbk91dHB1dCh0aGlzLCAnV2Vic2l0ZUJ1Y2tldE5hbWUnLCB7XG4gICAgICB2YWx1ZTogdGhpcy53ZWJzaXRlQnVja2V0LmJ1Y2tldE5hbWUsXG4gICAgICBkZXNjcmlwdGlvbjogJ0Zyb250ZW5kIFMzIGJ1Y2tldCBuYW1lJyxcbiAgICAgIGV4cG9ydE5hbWU6IGAke2Vudn0tV2Vic2l0ZUJ1Y2tldE5hbWVgLFxuICAgIH0pO1xuXG4gICAgbmV3IGNkay5DZm5PdXRwdXQodGhpcywgJ1dlYnNpdGVCdWNrZXRBcm4nLCB7XG4gICAgICB2YWx1ZTogdGhpcy53ZWJzaXRlQnVja2V0LmJ1Y2tldEFybixcbiAgICAgIGRlc2NyaXB0aW9uOiAnRnJvbnRlbmQgUzMgYnVja2V0IEFSTicsXG4gICAgICBleHBvcnROYW1lOiBgJHtlbnZ9LVdlYnNpdGVCdWNrZXRBcm5gLFxuICAgIH0pO1xuXG4gICAgbmV3IGNkay5DZm5PdXRwdXQodGhpcywgJ1dlYnNpdGVVcmwnLCB7XG4gICAgICB2YWx1ZTogdGhpcy5idWNrZXRXZWJzaXRlVXJsLFxuICAgICAgZGVzY3JpcHRpb246ICdGcm9udGVuZCB3ZWJzaXRlIFVSTCAoSFRUUCknLFxuICAgICAgZXhwb3J0TmFtZTogYCR7ZW52fS1XZWJzaXRlVXJsYCxcbiAgICB9KTtcblxuICAgIC8vIFRhZyByZXNvdXJjZXNcbiAgICBjZGsuVGFncy5vZih0aGlzKS5hZGQoJ0Vudmlyb25tZW50JywgZW52KTtcbiAgICBjZGsuVGFncy5vZih0aGlzKS5hZGQoJ1NlcnZpY2UnLCAnRWNob2VzLUZyb250ZW5kJyk7XG4gIH1cbn0iXX0=