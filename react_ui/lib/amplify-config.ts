import { ResourcesConfig } from 'aws-amplify';

const amplifyConfig: ResourcesConfig = {
  Auth: {
    Cognito: {
      userPoolId: process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID || '',
      userPoolClientId: process.env.NEXT_PUBLIC_COGNITO_USER_POOL_CLIENT_ID || '',
      signUpVerificationMethod: 'code',
      loginWith: {
        email: false,
        phone: false,
        username: true,
      },
      passwordFormat: {
        minLength: 8,
        requireLowercase: true,
        requireNumbers: true,
        requireSpecialCharacters: true,
        requireUppercase: true,
      },
    },
  },
};

export default amplifyConfig;