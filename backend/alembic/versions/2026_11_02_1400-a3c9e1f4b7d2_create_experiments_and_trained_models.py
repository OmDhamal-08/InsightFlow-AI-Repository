"""create_experiments_and_trained_models

Phase 10 (AutoML) and Phase 11 (Model Evaluation) tables.

Revision ID: a3c9e1f4b7d2
Revises: 1712d5b4bcc1
Create Date: 2026-11-02 14:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3c9e1f4b7d2'
down_revision: Union[str, None] = '1712d5b4bcc1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the experiments and trained_models tables."""
    op.create_table(
        'experiments',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('dataset_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('target_column', sa.String(length=255), nullable=False),
        sa.Column('task_type', sa.String(length=40), nullable=True),
        sa.Column('optimize_metric', sa.String(length=40), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('summary', sa.JSON(), nullable=True),
        sa.Column('best_model_id', sa.Uuid(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('training_time_seconds', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['dataset_id'], ['datasets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_experiments_dataset_id'), 'experiments', ['dataset_id'], unique=False)
    op.create_index(op.f('ix_experiments_user_id'), 'experiments', ['user_id'], unique=False)

    op.create_table(
        'trained_models',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('experiment_id', sa.Uuid(), nullable=False),
        sa.Column('algorithm', sa.String(length=50), nullable=False),
        sa.Column('display_name', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('hyperparameters', sa.JSON(), nullable=False),
        sa.Column('cv_score', sa.Float(), nullable=True),
        sa.Column('cv_std', sa.Float(), nullable=True),
        sa.Column('test_score', sa.Float(), nullable=True),
        sa.Column('metrics', sa.JSON(), nullable=False),
        sa.Column('evaluation', sa.JSON(), nullable=False),
        sa.Column('artifact_path', sa.String(length=500), nullable=True),
        sa.Column('training_time_seconds', sa.Float(), nullable=True),
        sa.Column('rank', sa.Integer(), nullable=True),
        sa.Column('is_best', sa.Boolean(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['experiment_id'], ['experiments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_trained_models_experiment_id'), 'trained_models', ['experiment_id'], unique=False)


def downgrade() -> None:
    """Drop the Phase 10/11 tables."""
    op.drop_index(op.f('ix_trained_models_experiment_id'), table_name='trained_models')
    op.drop_table('trained_models')
    op.drop_index(op.f('ix_experiments_user_id'), table_name='experiments')
    op.drop_index(op.f('ix_experiments_dataset_id'), table_name='experiments')
    op.drop_table('experiments')
