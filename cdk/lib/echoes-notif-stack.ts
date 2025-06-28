import * as cdk from 'aws-cdk-lib';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as lambdaEventSources from 'aws-cdk-lib/aws-lambda-event-sources';
import * as snsSubscriptions from 'aws-cdk-lib/aws-sns-subscriptions';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

export interface EchoesNotifStackProps extends cdk.StackProps {
  environment: string;
  table: dynamodb.Table;
}

export class EchoesNotifStack extends cdk.Stack {
  public readonly eventBus: events.EventBus;
  public readonly snsTopic: sns.Topic;
  public readonly notificationLambda: lambda.Function;

  constructor(scope: Construct, id: string, props: EchoesNotifStackProps) {
    super(scope, id, props);

    // Custom EventBridge bus for Echoes events
    this.eventBus = new events.EventBus(this, 'EchoesEventBus', {
      eventBusName: `echoes-events-${props.environment}`,
    });

    // SNS Topic for notifications
    this.snsTopic = new sns.Topic(this, 'EchoesNotificationTopic', {
      topicName: `echoes-notifications-${props.environment}`,
      displayName: 'Echoes Notifications',
    });

    // Dead letter queue for failed notifications
    const deadLetterQueue = new sqs.Queue(this, 'NotificationDLQ', {
      queueName: `echoes-notification-dlq-${props.environment}`,
      retentionPeriod: cdk.Duration.days(14),
    });

    // SQS Queue for processing notifications
    const notificationQueue = new sqs.Queue(this, 'NotificationQueue', {
      queueName: `echoes-notifications-${props.environment}`,
      visibilityTimeout: cdk.Duration.minutes(5),
      deadLetterQueue: {
        queue: deadLetterQueue,
        maxReceiveCount: 3,
      },
    });

    // Lambda role for notifications
    const notificationLambdaRole = new iam.Role(this, 'NotificationLambdaRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
    });

    // Permissions for DynamoDB
    props.table.grantReadData(notificationLambdaRole);

    // Permissions for SNS
    this.snsTopic.grantPublish(notificationLambdaRole);

    // Permissions for SQS
    notificationQueue.grantConsumeMessages(notificationLambdaRole);

    // Lambda function for processing notifications
    this.notificationLambda = new lambda.Function(this, 'NotificationLambda', {
      functionName: `echoes-notifications-${props.environment}`,
      runtime: lambda.Runtime.PYTHON_3_11,
      code: lambda.Code.fromInline(`
import json
import boto3
import logging
from datetime import datetime, timedelta

logger = logging.getLogger()
logger.setLevel(logging.INFO)

sns = boto3.client('sns')
dynamodb = boto3.resource('dynamodb')

def handler(event, context):
    """
    Process notification events from EventBridge or SQS
    """
    try:
        # Handle EventBridge events
        if 'source' in event and event['source'] == 'echoes.app':
            return handle_echo_event(event)
        
        # Handle SQS events
        if 'Records' in event:
            for record in event['Records']:
                if record.get('eventSource') == 'aws:sqs':
                    handle_sqs_message(record)
        
        return {
            'statusCode': 200,
            'body': json.dumps('Notifications processed successfully')
        }
        
    except Exception as e:
        logger.error(f"Error processing notifications: {e}")
        raise

def handle_echo_event(event):
    """Handle echo-related events"""
    detail = event.get('detail', {})
    event_type = detail.get('event_type')
    user_id = detail.get('user_id')
    
    if event_type == 'echo_created':
        schedule_reminder_notification(user_id, detail)
    elif event_type == 'reminder_due':
        send_reminder_notification(user_id, detail)
    
    return {'statusCode': 200}

def schedule_reminder_notification(user_id, echo_data):
    """Schedule future reminder notifications"""
    # This would typically create EventBridge scheduled rules
    # For now, just log the scheduling
    logger.info(f"Scheduling reminder for user {user_id}: {echo_data}")

def send_reminder_notification(user_id, reminder_data):
    """Send actual notification to user"""
    message = {
        'user_id': user_id,
        'type': 'echo_reminder',
        'title': 'An Echo wants to say hello',
        'body': f"Remember this {reminder_data.get('emotion', 'moment')} from the past?",
        'data': reminder_data
    }
    
    # Publish to SNS
    sns.publish(
        TopicArn=os.environ['SNS_TOPIC_ARN'],
        Message=json.dumps(message),
        Subject='Echo Reminder'
    )
    
    logger.info(f"Sent reminder notification to user {user_id}")

def handle_sqs_message(record):
    """Handle SQS message"""
    body = json.loads(record['body'])
    logger.info(f"Processing SQS message: {body}")
    # Process the message as needed
      `),
      handler: 'index.handler',
      role: notificationLambdaRole,
      environment: {
        ENVIRONMENT: props.environment,
        SNS_TOPIC_ARN: this.snsTopic.topicArn,
        DYNAMODB_TABLE_NAME: props.table.tableName,
        EVENT_BUS_NAME: this.eventBus.eventBusName,
      },
      timeout: cdk.Duration.minutes(5),
      memorySize: 256,
    });

    // EventBridge rules for different notification types

    // Rule for echo creation events
    const echoCreatedRule = new events.Rule(this, 'EchoCreatedRule', {
      eventBus: this.eventBus,
      ruleName: `echoes-echo-created-${props.environment}`,
      description: 'Trigger when a new echo is created',
      eventPattern: {
        source: ['echoes.app'],
        detailType: ['Echo Created'],
      },
    });

    echoCreatedRule.addTarget(new targets.LambdaFunction(this.notificationLambda));

    // Rule for scheduled reminders
    const reminderRule = new events.Rule(this, 'ReminderRule', {
      eventBus: this.eventBus,
      ruleName: `echoes-reminder-${props.environment}`,
      description: 'Trigger scheduled echo reminders',
      eventPattern: {
        source: ['echoes.app'],
        detailType: ['Echo Reminder'],
      },
    });

    reminderRule.addTarget(new targets.LambdaFunction(this.notificationLambda));

    // Add SQS as event source for the Lambda
    this.notificationLambda.addEventSource(
      new lambdaEventSources.SqsEventSource(notificationQueue, {
        batchSize: 10,
        maxBatchingWindow: cdk.Duration.seconds(5),
      })
    );

    // Subscribe SNS to SQS for reliable delivery
    this.snsTopic.addSubscription(
      new snsSubscriptions.SqsSubscription(notificationQueue, {
        rawMessageDelivery: true,
      })
    );

    // CloudWatch rule for daily processing (cleanup, maintenance)
    const dailyMaintenanceRule = new events.Rule(this, 'DailyMaintenanceRule', {
      ruleName: `echoes-daily-maintenance-${props.environment}`,
      description: 'Daily maintenance tasks',
      schedule: events.Schedule.cron({
        minute: '0',
        hour: '2', // 2 AM UTC
      }),
    });

    dailyMaintenanceRule.addTarget(new targets.LambdaFunction(this.notificationLambda));

    // Output important values
    new cdk.CfnOutput(this, 'EventBusArn', {
      value: this.eventBus.eventBusArn,
      description: 'EventBridge bus ARN',
      exportName: `${props.environment}-EventBusArn`,
    });

    new cdk.CfnOutput(this, 'EventBusName', {
      value: this.eventBus.eventBusName,
      description: 'EventBridge bus name',
      exportName: `${props.environment}-EventBusName`,
    });

    new cdk.CfnOutput(this, 'SnsTopicArn', {
      value: this.snsTopic.topicArn,
      description: 'SNS topic ARN for notifications',
      exportName: `${props.environment}-SnsTopicArn`,
    });

    new cdk.CfnOutput(this, 'NotificationLambdaArn', {
      value: this.notificationLambda.functionArn,
      description: 'Notification Lambda function ARN',
      exportName: `${props.environment}-NotificationLambdaArn`,
    });

    new cdk.CfnOutput(this, 'NotificationQueueUrl', {
      value: notificationQueue.queueUrl,
      description: 'SQS queue URL for notifications',
      exportName: `${props.environment}-NotificationQueueUrl`,
    });
  }
}