"""roster_visibility

Revision ID: 15401063d4e3
Revises: b2e694dfde35
Create Date: 2019-01-20 20:45:50.773097

"""

# revision identifiers, used by Alembic.

import sqlalchemy as sa

from alembic import op
from mailman.database.helpers import exists_in_db, is_sqlite


revision = '15401063d4e3'
down_revision = 'b2e694dfde35'


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    if not exists_in_db(
            op.get_bind(), 'mailinglist', 'member_roster_visibility'):
        op.add_column(                                       # pragma: nocover
            'mailinglist',
            sa.Column('member_roster_visibility', sa.Integer(), nullable=True))


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    if not is_sqlite(op.get_bind()):
        op.drop_column('mailinglist', 'member_roster_visibility')   # noqa: E501 # pragma: nocover
