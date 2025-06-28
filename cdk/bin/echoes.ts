#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { EchoesStorageStack } from '../lib/echoes-storage-stack';
import { EchoesAuthStack } from '../lib/echoes-auth-stack';
import { EchoesApiStack } from '../lib/echoes-api-stack';
import { EchoesNotifStack } from '../lib/echoes-notif-stack';

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

// Add dependencies
apiStack.addDependency(storageStack);
apiStack.addDependency(authStack);
notifStack.addDependency(storageStack);

// Add tags to all stacks
const tags = {
  Project: 'Echoes',
  Environment: environment,
  ManagedBy: 'CDK',
};

Object.values(tags).forEach(([key, value]) => {
  cdk.Tags.of(app).add(key, value);
});