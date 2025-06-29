import * as cdk from 'aws-cdk-lib';
import * as events from 'aws-cdk-lib/aws-events';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import { Construct } from 'constructs';
export interface EchoesNotifStackProps extends cdk.StackProps {
    environment: string;
    table: dynamodb.Table;
}
export declare class EchoesNotifStack extends cdk.Stack {
    readonly eventBus: events.EventBus;
    readonly snsTopic: sns.Topic;
    readonly notificationLambda: lambda.Function;
    constructor(scope: Construct, id: string, props: EchoesNotifStackProps);
}
