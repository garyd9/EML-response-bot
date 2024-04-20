from database.database import Database
from utils import discord_helpers, general_helpers
import discord
from errors import discord_errors, database_errors
from database.table_player import PlayerFields, PlayerRecord, PlayerTable, Regions
from database.table_team import TeamFields, TeamRecord, TeamTable
from database.table_team_player import (
    TeamPlayerFields,
    TeamPlayerRecord,
    TeamPlayerTable,
)
import constants


class ManagePlayers:
    """EML Player Management"""

    def __init__(self, database: Database):
        self.database = database
        self.table_player = PlayerTable(database)
        self.table_team = TeamTable(database)
        self.table_team_player = TeamPlayerTable(database)

    async def register_player(
        self,
        interaction: discord.Interaction,
        region: str,
    ):
        """Create a new Player"""
        try:
            # This could take a while
            await interaction.response.defer()
            # Get player info
            discord_id = interaction.user.id
            player_name = interaction.user.display_name
            allowed_regions = [r.value for r in Regions]
            region = await ManagePlayersHelpers.normalize_region(region)
            assert region, f"Region must be in {allowed_regions}"
            # Create Player record
            await self.table_player.create_player_record(
                discord_id=discord_id, player_name=player_name, region=region
            )
            # Add Player role
            await ManagePlayersHelpers.member_add_player_role(
                interaction.user, region=region
            )
            # Success
            message = f"Player '{player_name}' registered for region '{region}'"
            return await interaction.followup.send(message)
        except database_errors.EmlRecordAlreadyExists:
            message = f"Player already registered"
            await interaction.followup.send(message)
        except AssertionError as message:
            await interaction.followup.send(message)
        except Exception as error:
            message = f"Error: Something went wrong."
            await interaction.followup.send(message)
            raise error

    async def unregister_player(self, interaction: discord.Interaction):
        """Unregister a Player"""
        try:
            # This could take a while
            await interaction.response.defer()
            # Get Player info
            discord_id = interaction.user.id
            existing_player = await self.table_player.get_player_record(
                discord_id=discord_id
            )
            assert existing_player, "You are not registered."
            existing_player_id = await existing_player.get_field(PlayerFields.record_id)
            existing_team_players = (
                await self.table_team_player.get_team_player_records(
                    player_id=existing_player_id
                )
            )
            assert not existing_team_players, "You must leave your team first."
            # Remove Player role
            await ManagePlayersHelpers.member_remove_player_role(interaction.user)
            # Delete Player record
            await self.table_player.delete_player_record(existing_player)
            # Success
            message = f"You are no longer registered as a player"
            return await interaction.followup.send(message)
        except AssertionError as message:
            await interaction.followup.send(message)
        except Exception as error:
            message = f"Error: Something went wrong."
            await interaction.followup.send(message)
            raise error

    async def get_player_details(
        self,
        interaction: discord.Interaction,
        player_name: str = None,
        discord_id: str = None,
    ):
        """Get a Player by name or Discord ID"""
        try:
            # This could take a while
            await interaction.response.defer()
            # Get Player info
            assert player_name or discord_id, "No player_name or discord_id provided."
            player = await self.table_player.get_player_record(
                discord_id=discord_id, player_name=player_name
            )
            assert player, "Player not found."
            player_name = await player.get_field(PlayerFields.player_name)
            player_region = await player.get_field(PlayerFields.region)
            player_id = await player.get_field(PlayerFields.record_id)
            message_dict = {}
            message_dict["player"] = player_name
            message_dict["region"] = player_region
            # Get Team info
            team_players = await self.table_team_player.get_team_player_records(
                player_id=player_id
            )
            team_player = team_players[0] if team_players else None
            if team_player:
                team_id = await team_player.get_field(TeamPlayerFields.team_id)
                team = await self.table_team.get_team_record(record_id=team_id)
                team_name = await team.get_field(TeamFields.team_name)
                is_captain = await team_player.get_field(TeamPlayerFields.is_captain)
                is_co_cap = await team_player.get_field(TeamPlayerFields.is_co_captain)
                message_dict["team"] = team_name
                message_dict["is_captain"] = is_captain
                message_dict["is_co_captain"] = is_co_cap
            # Create Response
            message = await general_helpers.format_json(message_dict)
            message = await discord_helpers.code_block(message, language="json")
            return await interaction.followup.send(message)
        except AssertionError as message:
            await interaction.followup.send(message)
        except Exception as error:
            message = f"Error: Something went wrong."
            await interaction.followup.send(message)
            raise error


class ManagePlayersHelpers:
    """EML Player Management Helpers"""

    @staticmethod
    async def member_add_player_role(member: discord.Member, region: str):
        """Add a Captain role to a Guild Member"""
        role_name = f"{constants.ROLE_PREFIX_PLAYER}{region}"
        role = await discord_helpers.guild_role_get_or_create(member.guild, role_name)
        await member.add_roles(role)
        return True

    @staticmethod
    async def member_remove_player_role(member: discord.Member):
        """Remove a Captain role from a Guild Member"""
        prefixes = [constants.ROLE_PREFIX_PLAYER]
        for role in member.roles:
            if any(role.name.startswith(prefix) for prefix in prefixes):
                await member.remove_roles(role)
        return True

    @staticmethod
    async def normalize_region(region: str):
        """Normalize a region string"""
        allowed_regions = [r.value for r in Regions]
        for allowed_region in allowed_regions:
            if str(region).casefold() == str(allowed_region).casefold():
                return allowed_region
        return None
