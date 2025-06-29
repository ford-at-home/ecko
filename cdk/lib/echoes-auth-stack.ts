import * as cdk from 'aws-cdk-lib';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

export interface EchoesAuthStackProps extends cdk.StackProps {
  environment: string;
}

export class EchoesAuthStack extends cdk.Stack {
  public readonly userPool: cognito.UserPool;
  public readonly userPoolClient: cognito.UserPoolClient;
  public readonly identityPool: cognito.CfnIdentityPool;

  constructor(scope: Construct, id: string, props: EchoesAuthStackProps) {
    super(scope, id, props);

    // Cognito User Pool
    this.userPool = new cognito.UserPool(this, 'EchoesUserPool', {
      userPoolName: `echoes-users-${props.environment}`,
      signInAliases: {
        email: true,
        username: true,
      },
      autoVerify: {
        email: true,
      },
      passwordPolicy: {
        minLength: 8,
        requireUppercase: true,
        requireLowercase: true,
        requireDigits: true,
        requireSymbols: true,
      },
      accountRecovery: cognito.AccountRecovery.EMAIL_ONLY,
      selfSignUpEnabled: true,
      userVerification: {
        emailSubject: 'Welcome to Echoes - Verify your email',
        emailBody: 'Thanks for signing up to Echoes! Your verification code is {####}',
        emailStyle: cognito.VerificationEmailStyle.CODE,
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
        timezone: new cognito.StringAttribute({
          minLen: 1,
          maxLen: 50,
          mutable: true,
        }),
        preferences: new cognito.StringAttribute({
          minLen: 1,
          maxLen: 1000,
          mutable: true,
        }),
      },
      removalPolicy: props.environment === 'prod' 
        ? cdk.RemovalPolicy.RETAIN 
        : cdk.RemovalPolicy.DESTROY,
    });

    // User Pool Client
    this.userPoolClient = new cognito.UserPoolClient(this, 'EchoesUserPoolClient', {
      userPool: this.userPool,
      userPoolClientName: `echoes-client-${props.environment}`,
      generateSecret: false, // For frontend applications
      authFlows: {
        userPassword: true,
        userSrp: true,
        custom: true,
        adminUserPassword: true,
      },
      oAuth: {
        flows: {
          authorizationCodeGrant: true,
          implicitCodeGrant: true,
        },
        scopes: [
          cognito.OAuthScope.EMAIL,
          cognito.OAuthScope.OPENID,
          cognito.OAuthScope.PROFILE,
        ],
        callbackUrls: [
          'http://localhost:3000/callback', // Development
          'https://echoes.app/callback', // Production - update as needed
        ],
        logoutUrls: [
          'http://localhost:3000/', // Development
          'https://echoes.app/', // Production - update as needed
        ],
      },
      preventUserExistenceErrors: true,
      refreshTokenValidity: cdk.Duration.days(30),
      accessTokenValidity: cdk.Duration.hours(1),
      idTokenValidity: cdk.Duration.hours(1),
    });

    // User Pool Domain
    // Sanitize account ID to ensure it only contains lowercase letters, numbers, and hyphens
    const sanitizedAccountId = this.account.substring(0, 8).toLowerCase().replace(/[^a-z0-9]/g, '');
    const userPoolDomain = new cognito.UserPoolDomain(this, 'EchoesUserPoolDomain', {
      userPool: this.userPool,
      cognitoDomain: {
        domainPrefix: `echoes-${props.environment}-${sanitizedAccountId}`,
      },
    });

    // Identity Pool for authenticated access
    this.identityPool = new cognito.CfnIdentityPool(this, 'EchoesIdentityPool', {
      identityPoolName: `echoes_identity_pool_${props.environment}`,
      allowUnauthenticatedIdentities: false,
      cognitoIdentityProviders: [
        {
          clientId: this.userPoolClient.userPoolClientId,
          providerName: this.userPool.userPoolProviderName,
          serverSideTokenCheck: true,
        },
      ],
    });

    // IAM roles for authenticated users
    const authenticatedRole = new iam.Role(this, 'CognitoAuthenticatedRole', {
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
    });

    // Basic permissions for authenticated users
    authenticatedRole.addToPolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: [
        'mobileanalytics:PutEvents',
        'cognito-sync:*',
        'cognito-identity:*',
      ],
      resources: ['*'],
    }));

    // Attach roles to identity pool
    new cognito.CfnIdentityPoolRoleAttachment(this, 'IdentityPoolRoleAttachment', {
      identityPoolId: this.identityPool.ref,
      roles: {
        authenticated: authenticatedRole.roleArn,
      },
    });

    // Pre-sign up Lambda trigger (optional)
    // This could be used for custom validation logic
    
    // Output important values
    new cdk.CfnOutput(this, 'UserPoolId', {
      value: this.userPool.userPoolId,
      description: 'Cognito User Pool ID',
      exportName: `${props.environment}-UserPoolId`,
    });

    new cdk.CfnOutput(this, 'UserPoolClientId', {
      value: this.userPoolClient.userPoolClientId,
      description: 'Cognito User Pool Client ID',
      exportName: `${props.environment}-UserPoolClientId`,
    });

    new cdk.CfnOutput(this, 'IdentityPoolId', {
      value: this.identityPool.ref,
      description: 'Cognito Identity Pool ID',
      exportName: `${props.environment}-IdentityPoolId`,
    });

    new cdk.CfnOutput(this, 'UserPoolDomain', {
      value: userPoolDomain.domainName,
      description: 'Cognito User Pool Domain',
      exportName: `${props.environment}-UserPoolDomain`,
    });

    new cdk.CfnOutput(this, 'AuthenticatedRoleArn', {
      value: authenticatedRole.roleArn,
      description: 'IAM Role for authenticated users',
      exportName: `${props.environment}-AuthenticatedRoleArn`,
    });
  }
}