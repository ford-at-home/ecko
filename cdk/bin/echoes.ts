#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { EchoesStorageStack } from '../lib/echoes-storage-stack';
import { EchoesAuthStack } from '../lib/echoes-auth-stack';
import { EchoesApiStack } from '../lib/echoes-api-stack';
import { EchoesNotifStack } from '../lib/echoes-notif-stack';
import { EchoesFrontendStack } from '../lib/frontend-stack';
import { EchoesNetworkStack } from '../lib/network-stack';
import { FrontendConfig } from '../lib/frontend-config-construct';

const app = new cdk.App();

// Get environment configuration
const environment = app.node.tryGetContext('environment') || 'dev';
const account = app.node.tryGetContext('account') || process.env.CDK_DEFAULT_ACCOUNT;
const region = app.node.tryGetContext('region') || process.env.CDK_DEFAULT_REGION || 'us-east-1';

const env = { account, region };

// Stack naming convention
const stackPrefix = `Echoes-${environment}`;

// Storage stack (S3 + DynamoDB)
const storageStack = new EchoesStorageStack(app, `${stackPrefix}-Storage`, {
  env,
  description: `Echoes storage resources for ${environment} environment`,
  environment,
});

// Authentication stack (Cognito)
const authStack = new EchoesAuthStack(app, `${stackPrefix}-Auth`, {
  env,
  description: `Echoes authentication resources for ${environment} environment`,
  environment,
});

// API stack (Lambda + API Gateway)
const apiStack = new EchoesApiStack(app, `${stackPrefix}-Api`, {
  env,
  description: `Echoes API resources for ${environment} environment`,
  environment,
  bucket: storageStack.audioBucket,
  table: storageStack.echoesTable,
  userPool: authStack.userPool,
  userPoolClient: authStack.userPoolClient,
});

// Notifications stack (EventBridge + SNS)
const notifStack = new EchoesNotifStack(app, `${stackPrefix}-Notif`, {
  env,
  description: `Echoes notification resources for ${environment} environment`,
  environment,
  table: storageStack.echoesTable,
});

// Frontend stack (S3 static hosting)
const frontendStack = new EchoesFrontendStack(app, `${stackPrefix}-Frontend`, {
  env,
  description: `Echoes frontend hosting resources for ${environment} environment`,
  environment,
});

// Network stack (CloudFront CDN)
const networkStack = new EchoesNetworkStack(app, `${stackPrefix}-Network`, {
  env,
  description: `Echoes network resources for ${environment} environment`,
  environment,
  frontendBucket: frontendStack.websiteBucket,
  originAccessIdentity: frontendStack.originAccessIdentity,
  // Optional: Add custom domain if available
  // domainName: 'echoes.app',
});

// Create a separate stack for frontend configuration to avoid circular dependencies
const frontendConfigStack = new cdk.Stack(app, `${stackPrefix}-Config`, {
  env,
  description: `Echoes frontend configuration for ${environment} environment`,
});

// Frontend configuration - aggregates all outputs for frontend environment
const frontendConfig = new FrontendConfig(frontendConfigStack, 'FrontendConfig', {
  environment,
  apiUrl: apiStack.apiUrl,
  cognitoUserPoolId: authStack.userPool.userPoolId,
  cognitoClientId: authStack.userPoolClient.userPoolClientId,
  s3BucketName: storageStack.audioBucket.bucketName,
  cloudFrontUrl: networkStack.distribution.distributionDomainName,
  region: region,
});

// Add dependencies
apiStack.addDependency(storageStack);
apiStack.addDependency(authStack);
notifStack.addDependency(storageStack);
networkStack.addDependency(frontendStack);
// Frontend config depends on all stacks it references
frontendConfigStack.addDependency(apiStack);
frontendConfigStack.addDependency(authStack);
frontendConfigStack.addDependency(storageStack);
frontendConfigStack.addDependency(networkStack);

// Add tags to all stacks
const tags = {
  Project: 'Echoes',
  Environment: environment,
  ManagedBy: 'CDK',
};

Object.values(tags).forEach(([key, value]) => {
  cdk.Tags.of(app).add(key, value);
});