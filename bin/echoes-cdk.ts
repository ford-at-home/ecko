#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { EchoesStorageStack } from '../lib/echoes-storage-stack';
import { EchoesApiStack } from '../lib/echoes-api-stack';
import { EchoesAuthStack } from '../lib/echoes-auth-stack';
import { EchoesNotifStack } from '../lib/echoes-notif-stack';

const app = new cdk.App();

// Get environment from context or default to 'dev'
const environment = app.node.tryGetContext('environment') || 'dev';
const account = process.env.CDK_DEFAULT_ACCOUNT;
const region = process.env.CDK_DEFAULT_REGION || 'us-east-1';

const env = {
  account,
  region,
};

// Common tags for all resources
const commonTags = {
  Project: 'Echoes',
  Environment: environment,
  Owner: 'EchoesTeam',
  CostCenter: 'Engineering',
};

// Authentication Stack (foundational)
const authStack = new EchoesAuthStack(app, `Echoes-Auth-${environment}`, {
  env,
  environment,
  tags: commonTags,
});

// Storage Stack (foundational)
const storageStack = new EchoesStorageStack(app, `Echoes-Storage-${environment}`, {
  env,
  environment,
  tags: commonTags,
});

// API Stack (depends on storage and auth)
const apiStack = new EchoesApiStack(app, `Echoes-Api-${environment}`, {
  env,
  environment,
  userPool: authStack.userPool,
  identityPool: authStack.identityPool,
  echoesTable: storageStack.echoesTable,
  audiosBucket: storageStack.audiosBucket,
  tags: commonTags,
});

// Notification Stack (depends on storage)
const notifStack = new EchoesNotifStack(app, `Echoes-Notif-${environment}`, {
  env,
  environment,
  echoesTable: storageStack.echoesTable,
  tags: commonTags,
});

// Add stack dependencies
apiStack.addDependency(authStack);
apiStack.addDependency(storageStack);
notifStack.addDependency(storageStack);

// Output important values
new cdk.CfnOutput(apiStack, 'ApiEndpoint', {
  value: apiStack.api.url,
  description: 'API Gateway endpoint URL',
});

new cdk.CfnOutput(authStack, 'UserPoolId', {
  value: authStack.userPool.userPoolId,
  description: 'Cognito User Pool ID',
});

new cdk.CfnOutput(authStack, 'UserPoolClientId', {
  value: authStack.userPoolClient.userPoolClientId,
  description: 'Cognito User Pool Client ID',
});

new cdk.CfnOutput(authStack, 'IdentityPoolId', {
  value: authStack.identityPool.identityPoolId,
  description: 'Cognito Identity Pool ID',
});

new cdk.CfnOutput(storageStack, 'AudiosBucketName', {
  value: storageStack.audiosBucket.bucketName,
  description: 'S3 bucket for audio files',
});

new cdk.CfnOutput(storageStack, 'EchoesTableName', {
  value: storageStack.echoesTable.tableName,
  description: 'DynamoDB table for echo metadata',
});