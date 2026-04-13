import { Sequelize } from 'sequelize';
import { dbConfig } from '../config/database.js';
import { Icd } from './Icd.js';
import { Ops } from './Ops.js';

const sequelize = new Sequelize(
  dbConfig.database,
  dbConfig.username,
  dbConfig.password,
  dbConfig
);

const db = {
  sequelize,
  Sequelize,
  Icd,
  Ops,
};

// Initialize models with sequelize instance
Icd.init(sequelize);
Ops.init(sequelize);

// Define associations if needed (e.g. parent-child for hierarchy)
Icd.associate?.(db);
Ops.associate?.(db);

export { sequelize, Icd, Ops };
