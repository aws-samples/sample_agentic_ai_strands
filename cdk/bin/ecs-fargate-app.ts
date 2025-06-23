#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { EcsFargateStack } from '../lib/ecs-fargate-stack';

const app = new cdk.App();

// Read enableMem0 from context, default to true for backward compatibility
const enableMem0Context = app.node.tryGetContext('enableMem0');
const enableMem0 = enableMem0Context === 'false' ? false : true;

new EcsFargateStack(app, 'McpEcsFargateStack', {
  namePrefix: 'strands-mcp-app',
  enableMem0: enableMem0,
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION || 'us-east-1'
  },
});
