"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.EchoesNotifStack = void 0;
const cdk = require("aws-cdk-lib");
const events = require("aws-cdk-lib/aws-events");
const targets = require("aws-cdk-lib/aws-events-targets");
const sns = require("aws-cdk-lib/aws-sns");
const sqs = require("aws-cdk-lib/aws-sqs");
const lambda = require("aws-cdk-lib/aws-lambda");
const lambdaEventSources = require("aws-cdk-lib/aws-lambda-event-sources");
const snsSubscriptions = require("aws-cdk-lib/aws-sns-subscriptions");
const iam = require("aws-cdk-lib/aws-iam");
class EchoesNotifStack extends cdk.Stack {
    constructor(scope, id, props) {
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
        this.notificationLambda.addEventSource(new lambdaEventSources.SqsEventSource(notificationQueue, {
            batchSize: 10,
            maxBatchingWindow: cdk.Duration.seconds(5),
        }));
        // Subscribe SNS to SQS for reliable delivery
        this.snsTopic.addSubscription(new snsSubscriptions.SqsSubscription(notificationQueue, {
            rawMessageDelivery: true,
        }));
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
exports.EchoesNotifStack = EchoesNotifStack;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZWNob2VzLW5vdGlmLXN0YWNrLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiZWNob2VzLW5vdGlmLXN0YWNrLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7OztBQUFBLG1DQUFtQztBQUNuQyxpREFBaUQ7QUFDakQsMERBQTBEO0FBQzFELDJDQUEyQztBQUMzQywyQ0FBMkM7QUFDM0MsaURBQWlEO0FBQ2pELDJFQUEyRTtBQUMzRSxzRUFBc0U7QUFFdEUsMkNBQTJDO0FBUTNDLE1BQWEsZ0JBQWlCLFNBQVEsR0FBRyxDQUFDLEtBQUs7SUFLN0MsWUFBWSxLQUFnQixFQUFFLEVBQVUsRUFBRSxLQUE0QjtRQUNwRSxLQUFLLENBQUMsS0FBSyxFQUFFLEVBQUUsRUFBRSxLQUFLLENBQUMsQ0FBQztRQUV4QiwyQ0FBMkM7UUFDM0MsSUFBSSxDQUFDLFFBQVEsR0FBRyxJQUFJLE1BQU0sQ0FBQyxRQUFRLENBQUMsSUFBSSxFQUFFLGdCQUFnQixFQUFFO1lBQzFELFlBQVksRUFBRSxpQkFBaUIsS0FBSyxDQUFDLFdBQVcsRUFBRTtTQUNuRCxDQUFDLENBQUM7UUFFSCw4QkFBOEI7UUFDOUIsSUFBSSxDQUFDLFFBQVEsR0FBRyxJQUFJLEdBQUcsQ0FBQyxLQUFLLENBQUMsSUFBSSxFQUFFLHlCQUF5QixFQUFFO1lBQzdELFNBQVMsRUFBRSx3QkFBd0IsS0FBSyxDQUFDLFdBQVcsRUFBRTtZQUN0RCxXQUFXLEVBQUUsc0JBQXNCO1NBQ3BDLENBQUMsQ0FBQztRQUVILDZDQUE2QztRQUM3QyxNQUFNLGVBQWUsR0FBRyxJQUFJLEdBQUcsQ0FBQyxLQUFLLENBQUMsSUFBSSxFQUFFLGlCQUFpQixFQUFFO1lBQzdELFNBQVMsRUFBRSwyQkFBMkIsS0FBSyxDQUFDLFdBQVcsRUFBRTtZQUN6RCxlQUFlLEVBQUUsR0FBRyxDQUFDLFFBQVEsQ0FBQyxJQUFJLENBQUMsRUFBRSxDQUFDO1NBQ3ZDLENBQUMsQ0FBQztRQUVILHlDQUF5QztRQUN6QyxNQUFNLGlCQUFp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WyJpbXBvcnQgKiBhcyBjZGsgZnJvbSAnYXdzLWNkay1saWInO1xuaW1wb3J0ICogYXMgZXZlbnRzIGZyb20gJ2F3cy1jZGstbGliL2F3cy1ldmVudHMnO1xuaW1wb3J0ICogYXMgdGFyZ2V0cyBmcm9tICdhd3MtY2RrLWxpYi9hd3MtZXZlbnRzLXRhcmdldHMnO1xuaW1wb3J0ICogYXMgc25zIGZyb20gJ2F3cy1jZGstbGliL2F3cy1zbnMnO1xuaW1wb3J0ICogYXMgc3FzIGZyb20gJ2F3cy1jZGstbGliL2F3cy1zcXMnO1xuaW1wb3J0ICogYXMgbGFtYmRhIGZyb20gJ2F3cy1jZGstbGliL2F3cy1sYW1iZGEnO1xuaW1wb3J0ICogYXMgbGFtYmRhRXZlbnRTb3VyY2VzIGZyb20gJ2F3cy1jZGstbGliL2F3cy1sYW1iZGEtZXZlbnQtc291cmNlcyc7XG5pbXBvcnQgKiBhcyBzbnNTdWJzY3JpcHRpb25zIGZyb20gJ2F3cy1jZGstbGliL2F3cy1zbnMtc3Vic2NyaXB0aW9ucyc7XG5pbXBvcnQgKiBhcyBkeW5hbW9kYiBmcm9tICdhd3MtY2RrLWxpYi9hd3MtZHluYW1vZGInO1xuaW1wb3J0ICogYXMgaWFtIGZyb20gJ2F3cy1jZGstbGliL2F3cy1pYW0nO1xuaW1wb3J0IHsgQ29uc3RydWN0IH0gZnJvbSAnY29uc3RydWN0cyc7XG5cbmV4cG9ydCBpbnRlcmZhY2UgRWNob2VzTm90aWZTdGFja1Byb3BzIGV4dGVuZHMgY2RrLlN0YWNrUHJvcHMge1xuICBlbnZpcm9ubWVudDogc3RyaW5nO1xuICB0YWJsZTogZHluYW1vZGIuVGFibGU7XG59XG5cbmV4cG9ydCBjbGFzcyBFY2hvZXNOb3RpZlN0YWNrIGV4dGVuZHMgY2RrLlN0YWNrIHtcbiAgcHVibGljIHJlYWRvbmx5IGV2ZW50QnVzOiBldmVudHMuRXZlbnRCdXM7XG4gIHB1YmxpYyByZWFkb25seSBzbnNUb3BpYzogc25zLlRvcGljO1xuICBwdWJsaWMgcmVhZG9ubHkgbm90aWZpY2F0aW9uTGFtYmRhOiBsYW1iZGEuRnVuY3Rpb247XG5cbiAgY29uc3RydWN0b3Ioc2NvcGU6IENvbnN0cnVjdCwgaWQ6IHN0cmluZywgcHJvcHM6IEVjaG9lc05vdGlmU3RhY2tQcm9wcykge1xuICAgIHN1cGVyKHNjb3BlLCBpZCwgcHJvcHMpO1xuXG4gICAgLy8gQ3VzdG9tIEV2ZW50QnJpZGdlIGJ1cyBmb3IgRWNob2VzIGV2ZW50c1xuICAgIHRoaXMuZXZlbnRCdXMgPSBuZXcgZXZlbnRzLkV2ZW50QnVzKHRoaXMsICdFY2hvZXNFdmVudEJ1cycsIHtcbiAgICAgIGV2ZW50QnVzTmFtZTogYGVjaG9lcy1ldmVudHMtJHtwcm9wcy5lbnZpcm9ubWVudH1gLFxuICAgIH0pO1xuXG4gICAgLy8gU05TIFRvcGljIGZvciBub3RpZmljYXRpb25zXG4gICAgdGhpcy5zbnNUb3BpYyA9IG5ldyBzbnMuVG9waWModGhpcywgJ0VjaG9lc05vdGlmaWNhdGlvblRvcGljJywge1xuICAgICAgdG9waWNOYW1lOiBgZWNob2VzLW5vdGlmaWNhdGlvbnMtJHtwcm9wcy5lbnZpcm9ubWVudH1gLFxuICAgICAgZGlzcGxheU5hbWU6ICdFY2hvZXMgTm90aWZpY2F0aW9ucycsXG4gICAgfSk7XG5cbiAgICAvLyBEZWFkIGxldHRlciBxdWV1ZSBmb3IgZmFpbGVkIG5vdGlmaWNhdGlvbnNcbiAgICBjb25zdCBkZWFkTGV0dGVyUXVldWUgPSBuZXcgc3FzLlF1ZXVlKHRoaXMsICdOb3RpZmljYXRpb25ETFEnLCB7XG4gICAgICBxdWV1ZU5hbWU6IGBlY2hvZXMtbm90aWZpY2F0aW9uLWRscS0ke3Byb3BzLmVudmlyb25tZW50fWAsXG4gICAgICByZXRlbnRpb25QZXJpb2Q6IGNkay5EdXJhdGlvbi5kYXlzKDE0KSxcbiAgICB9KTtcblxuICAgIC8vIFNRUyBRdWV1ZSBmb3IgcHJvY2Vzc2luZyBub3RpZmljYXRpb25zXG4gICAgY29uc3Qgbm90aWZpY2F0aW9uUXVldWUgPSBuZXcgc3FzLlF1ZXVlKHRoaXMsICdOb3RpZmljYXRpb25RdWV1ZScsIHtcbiAgICAgIHF1ZXVlTmFtZTogYGVjaG9lcy1ub3RpZmljYXRpb25zLSR7cHJvcHMuZW52aXJvbm1lbnR9YCxcbiAgICAgIHZpc2liaWxpdHlUaW1lb3V0OiBjZGsuRHVyYXRpb24ubWludXRlcyg1KSxcbiAgICAgIGRlYWRMZXR0ZXJRdWV1ZToge1xuICAgICAgICBxdWV1ZTogZGVhZExldHRlclF1ZXVlLFxuICAgICAgICBtYXhSZWNlaXZlQ291bnQ6IDMsXG4gICAgICB9LFxuICAgIH0pO1xuXG4gICAgLy8gTGFtYmRhIHJvbGUgZm9yIG5vdGlmaWNhdGlvbnNcbiAgICBjb25zdCBub3RpZmljYXRpb25MYW1iZGFSb2xlID0gbmV3IGlhbS5Sb2xlKHRoaXMsICdOb3RpZmljYXRpb25MYW1iZGFSb2xlJywge1xuICAgICAgYXNzdW1lZEJ5OiBuZXcgaWFtLlNlcnZpY2VQcmluY2lwYWwoJ2xhbWJkYS5hbWF6b25hd3MuY29tJyksXG4gICAgICBtYW5hZ2VkUG9saWNpZXM6IFtcbiAgICAgICAgaWFtLk1hbmFnZWRQb2xpY3kuZnJvbUF3c01hbmFnZWRQb2xpY3lOYW1lKCdzZXJ2aWNlLXJvbGUvQVdTTGFtYmRhQmFzaWNFeGVjdXRpb25Sb2xlJyksXG4gICAgICBdLFxuICAgIH0pO1xuXG4gICAgLy8gUGVybWlzc2lvbnMgZm9yIER5bmFtb0RCXG4gICAgcHJvcHMudGFibGUuZ3JhbnRSZWFkRGF0YShub3RpZmljYXRpb25MYW1iZGFSb2xlKTtcblxuICAgIC8vIFBlcm1pc3Npb25zIGZvciBTTlNcbiAgICB0aGlzLnNuc1RvcGljLmdyYW50UHVibGlzaChub3RpZmljYXRpb25MYW1iZGFSb2xlKTtcblxuICAgIC8vIFBlcm1pc3Npb25zIGZvciBTUVNcbiAgICBub3RpZmljYXRpb25RdWV1ZS5ncmFudENvbnN1bWVNZXNzYWdlcyhub3RpZmljYXRpb25MYW1iZGFSb2xlKTtcblxuICAgIC8vIExhbWJkYSBmdW5jdGlvbiBmb3IgcHJvY2Vzc2luZyBub3RpZmljYXRpb25zXG4gICAgdGhpcy5ub3RpZmljYXRpb25MYW1iZGEgPSBuZXcgbGFtYmRhLkZ1bmN0aW9uKHRoaXMsICdOb3RpZmljYXRpb25MYW1iZGEnLCB7XG4gICAgICBmdW5jdGlvbk5hbWU6IGBlY2hvZXMtbm90aWZpY2F0aW9ucy0ke3Byb3BzLmVudmlyb25tZW50fWAsXG4gICAgICBydW50aW1lOiBsYW1iZGEuUnVudGltZS5QWVRIT05fM18xMSxcbiAgICAgIGNvZGU6IGxhbWJkYS5Db2RlLmZyb21JbmxpbmUoYFxuaW1wb3J0IGpzb25cbmltcG9ydCBib3RvM1xuaW1wb3J0IGxvZ2dpbmdcbmZyb20gZGF0ZXRpbWUgaW1wb3J0IGRhdGV0aW1lLCB0aW1lZGVsdGFcblxubG9nZ2VyID0gbG9nZ2luZy5nZXRMb2dnZXIoKVxubG9nZ2VyLnNldExldmVsKGxvZ2dpbmcuSU5GTylcblxuc25zID0gYm90bzMuY2xpZW50KCdzbnMnKVxuZHluYW1vZGIgPSBib3RvMy5yZXNvdXJjZSgnZHluYW1vZGInKVxuXG5kZWYgaGFuZGxlcihldmVudCwgY29udGV4dCk6XG4gICAgXCJcIlwiXG4gICAgUHJvY2VzcyBub3RpZmljYXRpb24gZXZlbnRzIGZyb20gRXZlbnRCcmlkZ2Ugb3IgU1FTXG4gICAgXCJcIlwiXG4gICAgdHJ5OlxuICAgICAgICAjIEhhbmRsZSBFdmVudEJyaWRnZSBldmVudHNcbiAgICAgICAgaWYgJ3NvdXJjZScgaW4gZXZlbnQgYW5kIGV2ZW50Wydzb3VyY2UnXSA9PSAnZWNob2VzLmFwcCc6XG4gICAgICAgICAgICByZXR1cm4gaGFuZGxlX2VjaG9fZXZlbnQoZXZlbnQpXG4gICAgICAgIFxuICAgICAgICAjIEhhbmRsZSBTUVMgZXZlbnRzXG4gICAgICAgIGlmICdSZWNvcmRzJyBpbiBldmVudDpcbiAgICAgICAgICAgIGZvciByZWNvcmQgaW4gZXZlbnRbJ1JlY29yZHMnXTpcbiAgICAgICAgICAgICAgICBpZiByZWNvcmQuZ2V0KCdldmVudFNvdXJjZScpID09ICdhd3M6c3FzJzpcbiAgICAgICAgICAgICAgICAgICAgaGFuZGxlX3Nxc19tZXNzYWdlKHJlY29yZClcbiAgICAgICAgXG4gICAgICAgIHJldHVybiB7XG4gICAgICAgICAgICAnc3RhdHVzQ29kZSc6IDIwMCxcbiAgICAgICAgICAgICdib2R5JzoganNvbi5kdW1wcygnTm90aWZpY2F0aW9ucyBwcm9jZXNzZWQgc3VjY2Vzc2Z1bGx5JylcbiAgICAgICAgfVxuICAgICAgICBcbiAgICBleGNlcHQgRXhjZXB0aW9uIGFzIGU6XG4gICAgICAgIGxvZ2dlci5lcnJvcihmXCJFcnJvciBwcm9jZXNzaW5nIG5vdGlmaWNhdGlvbnM6IHtlfVwiKVxuICAgICAgICByYWlzZVxuXG5kZWYgaGFuZGxlX2VjaG9fZXZlbnQoZXZlbnQpOlxuICAgIFwiXCJcIkhhbmRsZSBlY2hvLXJlbGF0ZWQgZXZlbnRzXCJcIlwiXG4gICAgZGV0YWlsID0gZXZlbnQuZ2V0KCdkZXRhaWwnLCB7fSlcbiAgICBldmVudF90eXBlID0gZGV0YWlsLmdldCgnZXZlbnRfdHlwZScpXG4gICAgdXNlcl9pZCA9IGRldGFpbC5nZXQoJ3VzZXJfaWQnKVxuICAgIFxuICAgIGlmIGV2ZW50X3R5cGUgPT0gJ2VjaG9fY3JlYXRlZCc6XG4gICAgICAgIHNjaGVkdWxlX3JlbWluZGVyX25vdGlmaWNhdGlvbih1c2VyX2lkLCBkZXRhaWwpXG4gICAgZWxpZiBldmVudF90eXBlID09ICdyZW1pbmRlcl9kdWUnOlxuICAgICAgICBzZW5kX3JlbWluZGVyX25vdGlmaWNhdGlvbih1c2VyX2lkLCBkZXRhaWwpXG4gICAgXG4gICAgcmV0dXJuIHsnc3RhdHVzQ29kZSc6IDIwMH1cblxuZGVmIHNjaGVkdWxlX3JlbWluZGVyX25vdGlmaWNhdGlvbih1c2VyX2lkLCBlY2hvX2RhdGEpOlxuICAgIFwiXCJcIlNjaGVkdWxlIGZ1dHVyZSByZW1pbmRlciBub3RpZmljYXRpb25zXCJcIlwiXG4gICAgIyBUaGlzIHdvdWxkIHR5cGljYWxseSBjcmVhdGUgRXZlbnRCcmlkZ2Ugc2NoZWR1bGVkIHJ1bGVzXG4gICAgIyBGb3Igbm93LCBqdXN0IGxvZyB0aGUgc2NoZWR1bGluZ1xuICAgIGxvZ2dlci5pbmZvKGZcIlNjaGVkdWxpbmcgcmVtaW5kZXIgZm9yIHVzZXIge3VzZXJfaWR9OiB7ZWNob19kYXRhfVwiKVxuXG5kZWYgc2VuZF9yZW1pbmRlcl9ub3RpZmljYXRpb24odXNlcl9pZCwgcmVtaW5kZXJfZGF0YSk6XG4gICAgXCJcIlwiU2VuZCBhY3R1YWwgbm90aWZpY2F0aW9uIHRvIHVzZXJcIlwiXCJcbiAgICBtZXNzYWdlID0ge1xuICAgICAgICAndXNlcl9pZCc6IHVzZXJfaWQsXG4gICAgICAgICd0eXBlJzogJ2VjaG9fcmVtaW5kZXInLFxuICAgICAgICAndGl0bGUnOiAnQW4gRWNobyB3YW50cyB0byBzYXkgaGVsbG8nLFxuICAgICAgICAnYm9keSc6IGZcIlJlbWVtYmVyIHRoaXMge3JlbWluZGVyX2RhdGEuZ2V0KCdlbW90aW9uJywgJ21vbWVudCcpfSBmcm9tIHRoZSBwYXN0P1wiLFxuICAgICAgICAnZGF0YSc6IHJlbWluZGVyX2RhdGFcbiAgICB9XG4gICAgXG4gICAgIyBQdWJsaXNoIHRvIFNOU1xuICAgIHNucy5wdWJsaXNoKFxuICAgICAgICBUb3BpY0Fybj1vcy5lbnZpcm9uWydTTlNfVE9QSUNfQVJOJ10sXG4gICAgICAgIE1lc3NhZ2U9anNvbi5kdW1wcyhtZXNzYWdlKSxcbiAgICAgICAgU3ViamVjdD0nRWNobyBSZW1pbmRlcidcbiAgICApXG4gICAgXG4gICAgbG9nZ2VyLmluZm8oZlwiU2VudCByZW1pbmRlciBub3RpZmljYXRpb24gdG8gdXNlciB7dXNlcl9pZH1cIilcblxuZGVmIGhhbmRsZV9zcXNfbWVzc2FnZShyZWNvcmQpOlxuICAgIFwiXCJcIkhhbmRsZSBTUVMgbWVzc2FnZVwiXCJcIlxuICAgIGJvZHkgPSBqc29uLmxvYWRzKHJlY29yZFsnYm9keSddKVxuICAgIGxvZ2dlci5pbmZvKGZcIlByb2Nlc3NpbmcgU1FTIG1lc3NhZ2U6IHtib2R5fVwiKVxuICAgICMgUHJvY2VzcyB0aGUgbWVzc2FnZSBhcyBuZWVkZWRcbiAgICAgIGApLFxuICAgICAgaGFuZGxlcjogJ2luZGV4LmhhbmRsZXInLFxuICAgICAgcm9sZTogbm90aWZpY2F0aW9uTGFtYmRhUm9sZSxcbiAgICAgIGVudmlyb25tZW50OiB7XG4gICAgICAgIEVOVklST05NRU5UOiBwcm9wcy5lbnZpcm9ubWVudCxcbiAgICAgICAgU05TX1RPUElDX0FSTjogdGhpcy5zbnNUb3BpYy50b3BpY0FybixcbiAgICAgICAgRFlOQU1PREJfVEFCTEVfTkFNRTogcHJvcHMudGFibGUudGFibGVOYW1lLFxuICAgICAgICBFVkVOVF9CVVNfTkFNRTogdGhpcy5ldmVudEJ1cy5ldmVudEJ1c05hbWUsXG4gICAgICB9LFxuICAgICAgdGltZW91dDogY2RrLkR1cmF0aW9uLm1pbnV0ZXMoNSksXG4gICAgICBtZW1vcnlTaXplOiAyNTYsXG4gICAgfSk7XG5cbiAgICAvLyBFdmVudEJyaWRnZSBydWxlcyBmb3IgZGlmZmVyZW50IG5vdGlmaWNhdGlvbiB0eXBlc1xuXG4gICAgLy8gUnVsZSBmb3IgZWNobyBjcmVhdGlvbiBldmVudHNcbiAgICBjb25zdCBlY2hvQ3JlYXRlZFJ1bGUgPSBuZXcgZXZlbnRzLlJ1bGUodGhpcywgJ0VjaG9DcmVhdGVkUnVsZScsIHtcbiAgICAgIGV2ZW50QnVzOiB0aGlzLmV2ZW50QnVzLFxuICAgICAgcnVsZU5hbWU6IGBlY2hvZXMtZWNoby1jcmVhdGVkLSR7cHJvcHMuZW52aXJvbm1lbnR9YCxcbiAgICAgIGRlc2NyaXB0aW9uOiAnVHJpZ2dlciB3aGVuIGEgbmV3IGVjaG8gaXMgY3JlYXRlZCcsXG4gICAgICBldmVudFBhdHRlcm46IHtcbiAgICAgICAgc291cmNlOiBbJ2VjaG9lcy5hcHAnXSxcbiAgICAgICAgZGV0YWlsVHlwZTogWydFY2hvIENyZWF0ZWQnXSxcbiAgICAgIH0sXG4gICAgfSk7XG5cbiAgICBlY2hvQ3JlYXRlZFJ1bGUuYWRkVGFyZ2V0KG5ldyB0YXJnZXRzLkxhbWJkYUZ1bmN0aW9uKHRoaXMubm90aWZpY2F0aW9uTGFtYmRhKSk7XG5cbiAgICAvLyBSdWxlIGZvciBzY2hlZHVsZWQgcmVtaW5kZXJzXG4gICAgY29uc3QgcmVtaW5kZXJSdWxlID0gbmV3IGV2ZW50cy5SdWxlKHRoaXMsICdSZW1pbmRlclJ1bGUnLCB7XG4gICAgICBldmVudEJ1czogdGhpcy5ldmVudEJ1cyxcbiAgICAgIHJ1bGVOYW1lOiBgZWNob2VzLXJlbWluZGVyLSR7cHJvcHMuZW52aXJvbm1lbnR9YCxcbiAgICAgIGRlc2NyaXB0aW9uOiAnVHJpZ2dlciBzY2hlZHVsZWQgZWNobyByZW1pbmRlcnMnLFxuICAgICAgZXZlbnRQYXR0ZXJuOiB7XG4gICAgICAgIHNvdXJjZTogWydlY2hvZXMuYXBwJ10sXG4gICAgICAgIGRldGFpbFR5cGU6IFsnRWNobyBSZW1pbmRlciddLFxuICAgICAgfSxcbiAgICB9KTtcblxuICAgIHJlbWluZGVyUnVsZS5hZGRUYXJnZXQobmV3IHRhcmdldHMuTGFtYmRhRnVuY3Rpb24odGhpcy5ub3RpZmljYXRpb25MYW1iZGEpKTtcblxuICAgIC8vIEFkZCBTUVMgYXMgZXZlbnQgc291cmNlIGZvciB0aGUgTGFtYmRhXG4gICAgdGhpcy5ub3RpZmljYXRpb25MYW1iZGEuYWRkRXZlbnRTb3VyY2UoXG4gICAgICBuZXcgbGFtYmRhRXZlbnRTb3VyY2VzLlNxc0V2ZW50U291cmNlKG5vdGlmaWNhdGlvblF1ZXVlLCB7XG4gICAgICAgIGJhdGNoU2l6ZTogMTAsXG4gICAgICAgIG1heEJhdGNoaW5nV2luZG93OiBjZGsuRHVyYXRpb24uc2Vjb25kcyg1KSxcbiAgICAgIH0pXG4gICAgKTtcblxuICAgIC8vIFN1YnNjcmliZSBTTlMgdG8gU1FTIGZvciByZWxpYWJsZSBkZWxpdmVyeVxuICAgIHRoaXMuc25zVG9waWMuYWRkU3Vic2NyaXB0aW9uKFxuICAgICAgbmV3IHNuc1N1YnNjcmlwdGlvbnMuU3FzU3Vic2NyaXB0aW9uKG5vdGlmaWNhdGlvblF1ZXVlLCB7XG4gICAgICAgIHJhd01lc3NhZ2VEZWxpdmVyeTogdHJ1ZSxcbiAgICAgIH0pXG4gICAgKTtcblxuICAgIC8vIENsb3VkV2F0Y2ggcnVsZSBmb3IgZGFpbHkgcHJvY2Vzc2luZyAoY2xlYW51cCwgbWFpbnRlbmFuY2UpXG4gICAgY29uc3QgZGFpbHlNYWludGVuYW5jZVJ1bGUgPSBuZXcgZXZlbnRzLlJ1bGUodGhpcywgJ0RhaWx5TWFpbnRlbmFuY2VSdWxlJywge1xuICAgICAgcnVsZU5hbWU6IGBlY2hvZXMtZGFpbHktbWFpbnRlbmFuY2UtJHtwcm9wcy5lbnZpcm9ubWVudH1gLFxuICAgICAgZGVzY3JpcHRpb246ICdEYWlseSBtYWludGVuYW5jZSB0YXNrcycsXG4gICAgICBzY2hlZHVsZTogZXZlbnRzLlNjaGVkdWxlLmNyb24oe1xuICAgICAgICBtaW51dGU6ICcwJyxcbiAgICAgICAgaG91cjogJzInLCAvLyAyIEFNIFVUQ1xuICAgICAgfSksXG4gICAgfSk7XG5cbiAgICBkYWlseU1haW50ZW5hbmNlUnVsZS5hZGRUYXJnZXQobmV3IHRhcmdldHMuTGFtYmRhRnVuY3Rpb24odGhpcy5ub3RpZmljYXRpb25MYW1iZGEpKTtcblxuICAgIC8vIE91dHB1dCBpbXBvcnRhbnQgdmFsdWVzXG4gICAgbmV3IGNkay5DZm5PdXRwdXQodGhpcywgJ0V2ZW50QnVzQXJuJywge1xuICAgICAgdmFsdWU6IHRoaXMuZXZlbnRCdXMuZXZlbnRCdXNBcm4sXG4gICAgICBkZXNjcmlwdGlvbjogJ0V2ZW50QnJpZGdlIGJ1cyBBUk4nLFxuICAgICAgZXhwb3J0TmFtZTogYCR7cHJvcHMuZW52aXJvbm1lbnR9LUV2ZW50QnVzQXJuYCxcbiAgICB9KTtcblxuICAgIG5ldyBjZGsuQ2ZuT3V0cHV0KHRoaXMsICdFdmVudEJ1c05hbWUnLCB7XG4gICAgICB2YWx1ZTogdGhpcy5ldmVudEJ1cy5ldmVudEJ1c05hbWUsXG4gICAgICBkZXNjcmlwdGlvbjogJ0V2ZW50QnJpZGdlIGJ1cyBuYW1lJyxcbiAgICAgIGV4cG9ydE5hbWU6IGAke3Byb3BzLmVudmlyb25tZW50fS1FdmVudEJ1c05hbWVgLFxuICAgIH0pO1xuXG4gICAgbmV3IGNkay5DZm5PdXRwdXQodGhpcywgJ1Nuc1RvcGljQXJuJywge1xuICAgICAgdmFsdWU6IHRoaXMuc25zVG9waWMudG9waWNBcm4sXG4gICAgICBkZXNjcmlwdGlvbjogJ1NOUyB0b3BpYyBBUk4gZm9yIG5vdGlmaWNhdGlvbnMnLFxuICAgICAgZXhwb3J0TmFtZTogYCR7cHJvcHMuZW52aXJvbm1lbnR9LVNuc1RvcGljQXJuYCxcbiAgICB9KTtcblxuICAgIG5ldyBjZGsuQ2ZuT3V0cHV0KHRoaXMsICdOb3RpZmljYXRpb25MYW1iZGFBcm4nLCB7XG4gICAgICB2YWx1ZTogdGhpcy5ub3RpZmljYXRpb25MYW1iZGEuZnVuY3Rpb25Bcm4sXG4gICAgICBkZXNjcmlwdGlvbjogJ05vdGlmaWNhdGlvbiBMYW1iZGEgZnVuY3Rpb24gQVJOJyxcbiAgICAgIGV4cG9ydE5hbWU6IGAke3Byb3BzLmVudmlyb25tZW50fS1Ob3RpZmljYXRpb25MYW1iZGFBcm5gLFxuICAgIH0pO1xuXG4gICAgbmV3IGNkay5DZm5PdXRwdXQodGhpcywgJ05vdGlmaWNhdGlvblF1ZXVlVXJsJywge1xuICAgICAgdmFsdWU6IG5vdGlmaWNhdGlvblF1ZXVlLnF1ZXVlVXJsLFxuICAgICAgZGVzY3JpcHRpb246ICdTUVMgcXVldWUgVVJMIGZvciBub3RpZmljYXRpb25zJyxcbiAgICAgIGV4cG9ydE5hbWU6IGAke3Byb3BzLmVudmlyb25tZW50fS1Ob3RpZmljYXRpb25RdWV1ZVVybGAsXG4gICAgfSk7XG4gIH1cbn0iXX0=