import { Model, DataTypes } from 'sequelize';

/**
 * OPS (Operationen- und Prozedurenschlüssel)
 * German classification for medical procedures and operations
 * Hierarchical: 3- to 6-character codes (e.g. 1-10, 1-100, 5-010.0)
 * Chapters: 1 (Diagnostic), 3 (Imaging), 5 (Surgical), 6 (Medications), 8 (Therapeutic), 9 (Ancillary)
 */
export class Ops extends Model {
  static init(sequelize) {
    return super.init(
      {
        id: {
          type: DataTypes.INTEGER,
          primaryKey: true,
          autoIncrement: true,
        },
        code: {
          type: DataTypes.STRING(12),
          allowNull: false,
          comment: 'OPS code (e.g. 1-100, 5-010.0)',
        },
        label: {
          type: DataTypes.TEXT,
          allowNull: false,
          comment: 'Class title / description (German)',
        },
        chapter: {
          type: DataTypes.SMALLINT,
          allowNull: false,
          comment: 'Chapter: 1, 3, 5, 6, 8, or 9',
        },
        parentCode: {
          type: DataTypes.STRING(12),
          allowNull: true,
          comment: 'Parent code for hierarchy (denormalized for queries)',
        },
        parentId: {
          type: DataTypes.INTEGER,
          allowNull: true,
          references: { model: 'ops', key: 'id' },
          comment: 'FK to parent for hierarchy',
        },
        level: {
          type: DataTypes.SMALLINT,
          allowNull: false,
          comment: 'Hierarchy level: 3, 4, 5, or 6',
        },
        versionYear: {
          type: DataTypes.SMALLINT,
          allowNull: false,
          comment: 'OPS version year (e.g. 2025)',
        },
        isTerminal: {
          type: DataTypes.BOOLEAN,
          defaultValue: true,
          comment: 'True if no subcategories exist',
        },
      },
      {
        sequelize,
        modelName: 'Ops',
        tableName: 'ops',
        indexes: [
          { unique: true, fields: ['code', 'versionYear'] },
          { fields: ['chapter', 'versionYear'] },
          { fields: ['parentCode', 'versionYear'] },
          { fields: ['parentId'] },
          { fields: ['versionYear'] },
        ],
      }
    );
  }

  static associate(db) {
    Ops.belongsTo(Ops, { as: 'parent', foreignKey: 'parentId' });
    Ops.hasMany(Ops, { as: 'children', foreignKey: 'parentId' });
  }
}
