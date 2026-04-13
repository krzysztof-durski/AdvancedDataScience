#!/usr/bin/env node
/**
 * Sync database schema - creates tables for ICD and OPS
 * Run: npm run db:migrate
 */
import { sequelize, Icd, Ops } from '../models/index.js';

async function migrate() {
  try {
    await sequelize.authenticate();
    console.log('Database connection established.');

    await sequelize.sync({ alter: true });
    console.log('Database schema synced successfully.');

    process.exit(0);
  } catch (error) {
    console.error('Migration failed:', error);
    process.exit(1);
  }
}

migrate();
