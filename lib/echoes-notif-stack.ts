import * as cdk from 'aws-cdk-lib';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as snsSubscriptions from 'aws-cdk-lib/aws-sns-subscriptions';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';

interface EchoesNotifStackProps extends cdk.StackProps {
  environment: string;
  echoesTable: dynamodb.Table;
}

export class EchoesNotifStack extends cdk.Stack {
  public readonly notificationTopic: sns.Topic;
  public readonly scheduledNotificationsRule: events.Rule;
  public readonly notificationProcessorFunction: lambda.Function;
  public readonly echoReminderFunction: lambda.Function;

  constructor(scope: Construct, id: string, props: EchoesNotifStackProps) {
    super(scope, id, props);

    const { environment, echoesTable } = props;

    // SNS Topic for notifications
    this.notificationTopic = new sns.Topic(this, 'EchoesNotificationTopic', {
      topicName: `echoes-notifications-${environment}`,
      displayName: 'Echoes Notification Topic',
      fifo: false,
    });

    // Lambda execution role for notification functions
    const notificationLambdaRole = new iam.Role(this, 'NotificationLambdaRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
      inlinePolicies: {
        NotificationPolicy: new iam.PolicyDocument({
          statements: [
            // DynamoDB permissions
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'dynamodb:GetItem',
                'dynamodb:PutItem',
                'dynamodb:UpdateItem',
                'dynamodb:Query',
                'dynamodb:Scan',
              ],
              resources: [
                echoesTable.tableArn,
                `${echoesTable.tableArn}/index/*`,
              ],
            }),
            // SNS permissions
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'sns:Publish',
                'sns:GetTopicAttributes',
              ],
              resources: [this.notificationTopic.topicArn],
            }),
            // SES permissions for email notifications
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'ses:SendEmail',
                'ses:SendRawEmail',
              ],
              resources: ['*'],
            }),
          ],
        }),
      },
    });

    // Lambda function to process notification events
    this.notificationProcessorFunction = new lambda.Function(this, 'NotificationProcessorFunction', {
      functionName: `echoes-notification-processor-${environment}`,
      runtime: lambda.Runtime.NODEJS_18_X,
      handler: 'index.handler',
      code: lambda.Code.fromInline(`
const AWS = require('aws-sdk');
const sns = new AWS.SNS();
const ses = new AWS.SES();

exports.handler = async (event) => {
  console.log('Notification event received:', JSON.stringify(event, null, 2));
  
  try {
    for (const record of event.Records) {
      const message = JSON.parse(record.body || record.Sns?.Message || '{}');
      const { type, userId, echoId, userEmail, message: notificationMessage } = message;
      
      switch (type) {
        case 'echo_reminder':
          await sendEchoReminder(userId, echoId, userEmail, notificationMessage);
          break;
        case 'weekly_summary':
          await sendWeeklySummary(userId, userEmail, message.summary);
          break;
        default:
          console.log('Unknown notification type:', type);
      }
    }
    
    return { statusCode: 200, body: 'Notifications processed successfully' };
  } catch (error) {
    console.error('Error processing notifications:', error);
    throw error;
  }
};

async function sendEchoReminder(userId, echoId, userEmail, message) {
  if (!userEmail) {
    console.log('No email provided for user:', userId);
    return;
  }
  
  const params = {
    Source: process.env.FROM_EMAIL || 'noreply@echoes.app',
    Destination: {
      ToAddresses: [userEmail],
    },
    Message: {
      Subject: {
        Data: '🌀 An Echo from your past wants to say hello',
        Charset: 'UTF-8',
      },
      Body: {
        Html: {
          Data: \`
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
              <h1 style="color: #4A90E2;">🌀 Echoes</h1>
              <p>Hello,</p>
              <p>\${message || 'An Echo from your past is ready to transport you back to a special moment.'}</p>
              <p>Open your Echoes app to listen and let the memories flow.</p>
              <p style="margin-top: 30px; font-size: 12px; color: #666;">
                This is an automated message from Echoes. You can manage your notification preferences in the app settings.
              </p>
            </div>
          \`,
          Charset: 'UTF-8',
        },
      },
    },
  };
  
  try {
    await ses.sendEmail(params).promise();
    console.log('Echo reminder sent to:', userEmail);
  } catch (error) {
    console.error('Error sending echo reminder:', error);
  }
}

async function sendWeeklySummary(userId, userEmail, summary) {
  if (!userEmail) {
    console.log('No email provided for user:', userId);
    return;
  }
  
  const params = {
    Source: process.env.FROM_EMAIL || 'noreply@echoes.app',
    Destination: {
      ToAddresses: [userEmail],
    },
    Message: {
      Subject: {
        Data: '🌀 Your weekly Echoes summary',
        Charset: 'UTF-8',
      },
      Body: {
        Html: {
          Data: \`
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
              <h1 style="color: #4A90E2;">🌀 Echoes Weekly Summary</h1>
              <p>Hello,</p>
              <p>Here's what happened with your Echoes this week:</p>
              <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                \${summary}
              </div>
              <p>Keep capturing those beautiful moments!</p>
              <p style="margin-top: 30px; font-size: 12px; color: #666;">
                This is an automated message from Echoes. You can manage your notification preferences in the app settings.
              </p>
            </div>
          \`,
          Charset: 'UTF-8',
        },
      },
    },
  };
  
  try {
    await ses.sendEmail(params).promise();
    console.log('Weekly summary sent to:', userEmail);
  } catch (error) {
    console.error('Error sending weekly summary:', error);
  }
}
      `),
      environment: {
        ECHOES_TABLE_NAME: echoesTable.tableName,
        NOTIFICATION_TOPIC_ARN: this.notificationTopic.topicArn,
        ENVIRONMENT: environment,
        FROM_EMAIL: `noreply@echoes-${environment}.app`,
      },
      role: notificationLambdaRole,
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
      logRetention: logs.RetentionDays.ONE_MONTH,
    });

    // Lambda function to find and schedule echo reminders
    this.echoReminderFunction = new lambda.Function(this, 'EchoReminderFunction', {
      functionName: `echoes-reminder-scheduler-${environment}`,
      runtime: lambda.Runtime.NODEJS_18_X,
      handler: 'index.handler',
      code: lambda.Code.fromInline(`
const AWS = require('aws-sdk');
const dynamodb = new AWS.DynamoDB.DocumentClient();
const sns = new AWS.SNS();

exports.handler = async (event) => {
  console.log('Echo reminder scheduler triggered');
  
  try {
    // Calculate date ranges for reminders
    const now = new Date();
    const oneWeekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
    const oneMonthAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
    const threeMonthsAgo = new Date(now.getTime() - 90 * 24 * 60 * 60 * 1000);
    
    // Find echoes that qualify for reminders
    const scanParams = {
      TableName: process.env.ECHOES_TABLE_NAME,
      FilterExpression: 'isActive = :isActive AND (nextNotificationTime <= :now OR attribute_not_exists(nextNotificationTime))',
      ExpressionAttributeValues: {
        ':isActive': true,
        ':now': now.toISOString(),
      },
    };
    
    const result = await dynamodb.scan(scanParams).promise();
    
    for (const echo of result.Items || []) {
      const echoDate = new Date(echo.timestamp);
      const daysSinceEcho = Math.floor((now - echoDate) / (1000 * 60 * 60 * 24));
      
      // Determine if this echo should trigger a reminder
      let shouldRemind = false;
      let reminderMessage = '';
      let nextNotificationTime = null;
      
      if (daysSinceEcho === 7) {
        shouldRemind = true;
        reminderMessage = 'A week ago, you captured a moment. Ready to revisit it?';
        nextNotificationTime = new Date(now.getTime() + 23 * 24 * 60 * 60 * 1000); // 23 days later (30 total)
      } else if (daysSinceEcho === 30) {
        shouldRemind = true;
        reminderMessage = 'A month ago, you saved an Echo. Let it transport you back.';
        nextNotificationTime = new Date(now.getTime() + 60 * 24 * 60 * 60 * 1000); // 60 days later (90 total)
      } else if (daysSinceEcho === 90) {
        shouldRemind = true;
        reminderMessage = 'Three months ago, you captured something special. Time to remember.';
        nextNotificationTime = new Date(now.getTime() + 275 * 24 * 60 * 60 * 1000); // 275 days later (365 total)
      } else if (daysSinceEcho === 365) {
        shouldRemind = true;
        reminderMessage = 'A year ago today, you created this Echo. A perfect time to revisit.';
        nextNotificationTime = new Date(now.getTime() + 365 * 24 * 60 * 60 * 1000); // 1 year later
      }
      
      if (shouldRemind) {
        // Send notification
        const notificationMessage = {
          type: 'echo_reminder',
          userId: echo.userId,
          echoId: echo.echoId,
          userEmail: echo.userEmail, // Assume email is stored in echo metadata
          message: reminderMessage,
          emotion: echo.emotion,
          originalDate: echo.timestamp,
        };
        
        await sns.publish({
          TopicArn: process.env.NOTIFICATION_TOPIC_ARN,
          Message: JSON.stringify(notificationMessage),
          Subject: 'Echo Reminder',
        }).promise();
        
        // Update next notification time
        if (nextNotificationTime) {
          await dynamodb.update({
            TableName: process.env.ECHOES_TABLE_NAME,
            Key: {
              userId: echo.userId,
              echoId: echo.echoId,
            },
            UpdateExpression: 'SET nextNotificationTime = :nextTime',
            ExpressionAttributeValues: {
              ':nextTime': nextNotificationTime.toISOString(),
            },
          }).promise();
        }
        
        console.log(\`Reminder sent for echo: \${echo.echoId}\`);
      }
    }
    
    console.log(\`Processed \${result.Items?.length || 0} echoes for reminders\`);
    return { statusCode: 200, body: 'Reminder processing completed' };
  } catch (error) {
    console.error('Error processing echo reminders:', error);
    throw error;
  }
};
      `),
      environment: {
        ECHOES_TABLE_NAME: echoesTable.tableName,
        NOTIFICATION_TOPIC_ARN: this.notificationTopic.topicArn,
        ENVIRONMENT: environment,
      },
      role: notificationLambdaRole,
      timeout: cdk.Duration.minutes(5),
      memorySize: 512,
      logRetention: logs.RetentionDays.ONE_MONTH,
    });

    // Subscribe the notification processor to the SNS topic
    this.notificationTopic.addSubscription(
      new snsSubscriptions.LambdaSubscription(this.notificationProcessorFunction)
    );

    // EventBridge rule to trigger echo reminders daily
    this.scheduledNotificationsRule = new events.Rule(this, 'ScheduledNotificationsRule', {
      ruleName: `echoes-scheduled-notifications-${environment}`,
      description: 'Triggers daily echo reminder processing',
      schedule: events.Schedule.cron({
        minute: '0',
        hour: '10', // 10 AM UTC
        day: '*',
        month: '*',
        year: '*',
      }),
      targets: [new targets.LambdaFunction(this.echoReminderFunction)],
    });

    // Weekly summary rule (every Sunday at 9 AM UTC)
    const weeklySummaryRule = new events.Rule(this, 'WeeklySummaryRule', {
      ruleName: `echoes-weekly-summary-${environment}`,
      description: 'Triggers weekly echo summary generation',
      schedule: events.Schedule.cron({
        minute: '0',
        hour: '9',
        weekDay: 'SUN',
        month: '*',
        year: '*',
      }),
    });

    // Weekly summary Lambda function
    const weeklySummaryFunction = new lambda.Function(this, 'WeeklySummaryFunction', {
      functionName: `echoes-weekly-summary-${environment}`,
      runtime: lambda.Runtime.NODEJS_18_X,
      handler: 'index.handler',
      code: lambda.Code.fromInline(`
const AWS = require('aws-sdk');
const dynamodb = new AWS.DynamoDB.DocumentClient();
const sns = new AWS.SNS();

exports.handler = async (event) => {
  console.log('Weekly summary generation triggered');
  
  try {
    // Get all users who have been active in the last week
    const oneWeekAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
    
    const scanParams = {
      TableName: process.env.ECHOES_TABLE_NAME,
      FilterExpression: '#timestamp >= :weekAgo AND isActive = :isActive',
      ExpressionAttributeNames: {
        '#timestamp': 'timestamp',
      },
      ExpressionAttributeValues: {
        ':weekAgo': oneWeekAgo.toISOString(),
        ':isActive': true,
      },
    };
    
    const result = await dynamodb.scan(scanParams).promise();
    const userEchoes = {};
    
    // Group echoes by user
    for (const echo of result.Items || []) {
      if (!userEchoes[echo.userId]) {
        userEchoes[echo.userId] = [];
      }
      userEchoes[echo.userId].push(echo);
    }
    
    // Generate and send summary for each user
    for (const [userId, echoes] of Object.entries(userEchoes)) {
      const emotionCounts = {};
      let totalDuration = 0;
      
      echoes.forEach(echo => {
        emotionCounts[echo.emotion] = (emotionCounts[echo.emotion] || 0) + 1;
        totalDuration += echo.duration || 0;
      });
      
      const topEmotion = Object.keys(emotionCounts).reduce((a, b) => 
        emotionCounts[a] > emotionCounts[b] ? a : b
      );
      
      const summary = \`
        <p><strong>This week you created \${echoes.length} new Echo\${echoes.length > 1 ? 's' : ''}!</strong></p>
        <p>Your most frequent emotion was <strong>\${topEmotion}</strong> (\${emotionCounts[topEmotion]} time\${emotionCounts[topEmotion] > 1 ? 's' : ''}).</p>
        <p>Total recording time: \${Math.round(totalDuration)} seconds of captured memories.</p>
        <p>Keep building your personal time machine! 🌀</p>
      \`;
      
      const notificationMessage = {
        type: 'weekly_summary',
        userId,
        userEmail: echoes[0].userEmail, // Assume email is in echo metadata
        summary,
        echoCount: echoes.length,
        topEmotion,
      };
      
      await sns.publish({
        TopicArn: process.env.NOTIFICATION_TOPIC_ARN,
        Message: JSON.stringify(notificationMessage),
        Subject: 'Weekly Summary',
      }).promise();
      
      console.log(\`Weekly summary sent for user: \${userId}\`);
    }
    
    console.log(\`Generated weekly summaries for \${Object.keys(userEchoes).length} users\`);
    return { statusCode: 200, body: 'Weekly summaries sent' };
  } catch (error) {
    console.error('Error generating weekly summaries:', error);
    throw error;
  }
};
      `),
      environment: {
        ECHOES_TABLE_NAME: echoesTable.tableName,
        NOTIFICATION_TOPIC_ARN: this.notificationTopic.topicArn,
        ENVIRONMENT: environment,
      },
      role: notificationLambdaRole,
      timeout: cdk.Duration.minutes(5),
      memorySize: 512,
      logRetention: logs.RetentionDays.ONE_MONTH,
    });

    weeklySummaryRule.addTarget(new targets.LambdaFunction(weeklySummaryFunction));

    // CloudWatch alarms
    const notificationErrorAlarm = new cdk.aws_cloudwatch.Alarm(this, 'NotificationErrorAlarm', {
      metric: this.notificationProcessorFunction.metricErrors(),
      threshold: 5,
      evaluationPeriods: 2,
      alarmDescription: 'Notification processor errors exceed threshold',
    });

    const reminderErrorAlarm = new cdk.aws_cloudwatch.Alarm(this, 'ReminderErrorAlarm', {
      metric: this.echoReminderFunction.metricErrors(),
      threshold: 3,
      evaluationPeriods: 2,
      alarmDescription: 'Echo reminder function errors exceed threshold',
    });

    // Add tags
    cdk.Tags.of(this.notificationTopic).add('Component', 'Notifications');
    cdk.Tags.of(this.notificationProcessorFunction).add('Component', 'Notifications');
    cdk.Tags.of(this.echoReminderFunction).add('Component', 'Notifications');
    cdk.Tags.of(this.scheduledNotificationsRule).add('Component', 'Notifications');
  }
}