import * as cdk from 'aws-cdk-lib';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

interface EchoesAuthStackProps extends cdk.StackProps {
  environment: string;
}

export class EchoesAuthStack extends cdk.Stack {
  public readonly userPool: cognito.UserPool;
  public readonly userPoolClient: cognito.UserPoolClient;
  public readonly identityPool: cognito.CfnIdentityPool;
  public readonly authenticatedRole: iam.Role;
  public readonly unauthenticatedRole: iam.Role;

  constructor(scope: Construct, id: string, props: EchoesAuthStackProps) {
    super(scope, id, props);

    const { environment } = props;

    // Cognito User Pool
    this.userPool = new cognito.UserPool(this, 'EchoesUserPool', {
      userPoolName: `echoes-user-pool-${environment}`,
      selfSignUpEnabled: true,
      signInAliases: {
        email: true,
        username: true,
      },
      autoVerify: {
        email: true,
      },
      standardAttributes: {
        email: {
          required: true,
          mutable: true,
        },
        givenName: {
          required: false,
          mutable: true,
        },
        familyName: {
          required: false,
          mutable: true,
        },
      },
      customAttributes: {
        timezone: new cognito.StringAttribute({ minLen: 3, maxLen: 50, mutable: true }),
        preferredEmotion: new cognito.StringAttribute({ minLen: 3, maxLen: 20, mutable: true }),
      },
      passwordPolicy: {
        minLength: 8,
        requireLowercase: true,
        requireUppercase: true,
        requireDigits: true,
        requireSymbols: false,
      },
      accountRecovery: cognito.AccountRecovery.EMAIL_ONLY,
      removalPolicy: environment === 'prod' ? cdk.RemovalPolicy.RETAIN : cdk.RemovalPolicy.DESTROY,
    });

    // User Pool Client
    this.userPoolClient = new cognito.UserPoolClient(this, 'EchoesUserPoolClient', {
      userPool: this.userPool,
      userPoolClientName: `echoes-client-${environment}`,
      authFlows: {
        adminUserPassword: true,
        userPassword: true,
        userSrp: true,
        custom: true,
      },
      supportedIdentityProviders: [
        cognito.UserPoolClientIdentityProvider.COGNITO,
      ],
      generateSecret: false, // For mobile/web apps
      preventUserExistenceErrors: true,
      refreshTokenValidity: cdk.Duration.days(30),
      accessTokenValidity: cdk.Duration.hours(1),
      idTokenValidity: cdk.Duration.hours(1),
    });

    // Identity Pool for federated identities
    this.identityPool = new cognito.CfnIdentityPool(this, 'EchoesIdentityPool', {
      identityPoolName: `echoes_identity_pool_${environment}`,
      allowUnauthenticatedIdentities: false,
      cognitoIdentityProviders: [
        {
          clientId: this.userPoolClient.userPoolClientId,
          providerName: this.userPool.userPoolProviderName,
        },
      ],
    });

    // IAM Role for authenticated users
    this.authenticatedRole = new iam.Role(this, 'AuthenticatedRole', {
      assumedBy: new iam.FederatedPrincipal(
        'cognito-identity.amazonaws.com',
        {
          StringEquals: {
            'cognito-identity.amazonaws.com:aud': this.identityPool.ref,
          },
          'ForAnyValue:StringLike': {
            'cognito-identity.amazonaws.com:amr': 'authenticated',
          },
        },
        'sts:AssumeRoleWithWebIdentity'
      ),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('AmazonCognitoPowerUser'),
      ],
      inlinePolicies: {
        EchoesUserPolicy: new iam.PolicyDocument({
          statements: [
            // S3 permissions for user's own audio files
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                's3:GetObject',
                's3:PutObject',
                's3:DeleteObject',
              ],
              resources: [
                `arn:aws:s3:::echoes-audio-${environment}/\${cognito-identity.amazonaws.com:sub}/*`,
              ],
            }),
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                's3:ListBucket',
              ],
              resources: [
                `arn:aws:s3:::echoes-audio-${environment}`,
              ],
              conditions: {
                StringLike: {
                  's3:prefix': ['${cognito-identity.amazonaws.com:sub}/*'],
                },
              },
            }),
            // DynamoDB permissions for user's own echoes
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'dynamodb:GetItem',
                'dynamodb:PutItem',
                'dynamodb:UpdateItem',
                'dynamodb:DeleteItem',
                'dynamodb:Query',
              ],
              resources: [
                `arn:aws:dynamodb:${this.region}:${this.account}:table/EchoesTable-${environment}`,
                `arn:aws:dynamodb:${this.region}:${this.account}:table/EchoesTable-${environment}/index/*`,
              ],
              conditions: {
                'ForAllValues:StringEquals': {
                  'dynamodb:LeadingKeys': ['${cognito-identity.amazonaws.com:sub}'],
                },
              },
            }),
          ],
        }),
      },
    });

    // IAM Role for unauthenticated users (limited access)
    this.unauthenticatedRole = new iam.Role(this, 'UnauthenticatedRole', {
      assumedBy: new iam.FederatedPrincipal(
        'cognito-identity.amazonaws.com',
        {
          StringEquals: {
            'cognito-identity.amazonaws.com:aud': this.identityPool.ref,
          },
          'ForAnyValue:StringLike': {
            'cognito-identity.amazonaws.com:amr': 'unauthenticated',
          },
        },
        'sts:AssumeRoleWithWebIdentity'
      ),
      inlinePolicies: {
        EchoesUnauthenticatedPolicy: new iam.PolicyDocument({
          statements: [
            // Very limited permissions for unauthenticated users
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'mobileanalytics:PutEvents',
                'cognito-sync:*',
              ],
              resources: ['*'],
            }),
          ],
        }),
      },
    });

    // Attach roles to identity pool
    new cognito.CfnIdentityPoolRoleAttachment(this, 'IdentityPoolRoleAttachment', {
      identityPoolId: this.identityPool.ref,
      roles: {
        authenticated: this.authenticatedRole.roleArn,
        unauthenticated: this.unauthenticatedRole.roleArn,
      },
    });

    // User Pool Domain for hosted UI (optional)
    const userPoolDomain = new cognito.UserPoolDomain(this, 'EchoesUserPoolDomain', {
      userPool: this.userPool,
      cognitoDomain: {
        domainPrefix: `echoes-${environment}-${this.account}`,
      },
    });

    // Add tags
    cdk.Tags.of(this.userPool).add('Component', 'Authentication');
    cdk.Tags.of(this.identityPool).add('Component', 'Authentication');
    cdk.Tags.of(this.authenticatedRole).add('Component', 'Security');
    cdk.Tags.of(this.unauthenticatedRole).add('Component', 'Security');

    // Output the hosted UI URL
    new cdk.CfnOutput(this, 'HostedUIUrl', {
      value: `https://${userPoolDomain.domainName}.auth.${this.region}.amazoncognito.com`,
      description: 'Cognito Hosted UI URL',
    });
  }
}