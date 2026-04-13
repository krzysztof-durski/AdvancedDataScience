import { Model, DataTypes } from 'sequelize';

/**
 * ICD-10-GM (International Classification of Diseases, German Modification)
 * Hierarchical classification: 3-, 4-, or 5-character codes (e.g. A00, A00.0, A00.00)
 */
export class Icd extends Model {
  static init(sequelize) {
    return super.init(
      {
        id: {
          type: DataTypes.INTEGER,
          primaryKey: true,
          autoIncrement: true,
        },
        code: {
          type: DataTypes.STRING(10),
          allowNull: false,
          comment: 'Normalized code (e.g. A00.0, D27)',
        },
        label: {
          type: DataTypes.TEXT,
          allowNull: false,
          comment: 'Class title / description (German)',
        },
        category3: {
          type: DataTypes.STRING(4),
          allowNull: false,
          comment: 'Three-character category (e.g. A00, D27)',
        },
        parentCode: {
          type: DataTypes.STRING(10),
          allowNull: true,
          comment: 'Parent code for hierarchy (denormalized for queries)',
        },
        parentId: {
          type: DataTypes.INTEGER,
          allowNull: true,
          references: { model: 'icd', key: 'id' },
          comment: 'FK to parent for hierarchy',
        },
        level: {
          type: DataTypes.SMALLINT,
          allowNull: false,
          comment: 'Hierarchy level: 3, 4, or 5',
        },
        versionYear: {
          type: DataTypes.SMALLINT,
          allowNull: false,
          comment: 'ICD-10-GM version year (e.g. 2025)',
        },
        isTerminal: {
          type: DataTypes.BOOLEAN,
          defaultValue: true,
          comment: 'True if no subcategories exist',
        },
        codeType: {
          type: DataTypes.ENUM('primary', 'dagger', 'asterisk', 'exclamation'),
          defaultValue: 'primary',
          comment: 'dagger=aetiology, asterisk=manifestation, exclamation=optional',
        },
      },
      {
        sequelize,
        modelName: 'Icd',
        tableName: 'icd',
        indexes: [
          { unique: true, fields: ['code', 'versionYear'] },
          { fields: ['category3', 'versionYear'] },
          { fields: ['parentCode', 'versionYear'] },
          { fields: ['parentId'] },
          { fields: ['versionYear'] },
        ],
      }
    );
  }

  static associate(db) {
    Icd.belongsTo(Icd, { as: 'parent', foreignKey: 'parentId' });
    Icd.hasMany(Icd, { as: 'children', foreignKey: 'parentId' });
  }
}
