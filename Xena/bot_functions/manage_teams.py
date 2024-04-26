import utils.general_helpers as bot_helpers
from utils import discord_helpers
from database.database import Database
import constants
import discord
import errors.database_errors as DbErrors
from database.table_player import PlayerFields, PlayerRecord, PlayerTable
from database.table_team import TeamFields, TeamRecord, TeamTable
from database.table_team_player import (
    TeamPlayerFields,
    TeamPlayerRecord,
    TeamPlayerTable,
)


class ManageTeams:
    """EML Team Management"""

    def __init__(self, database: Database):
        self.database = database
        self.table_team = TeamTable(database)
        self.table_player = PlayerTable(database)
        self.table_team_player = TeamPlayerTable(database)

    async def register_team(self, interaction: discord.Interaction, team_name: str):
        """Create a Team with the given name

        Process:
        - Check if the Player is registered
        - Check if the Player is already on a Team
        - Check if the Team already exists
        - Create the Team and Captain Database Records
        - Update Discord roles
        """
        try:
            # This could take a while
            await interaction.response.defer()
            # Check if the Player is registered
            discord_id = interaction.user.id
            player = await self.table_player.get_player_record(discord_id=discord_id)
            assert player, f"You must be registered as a player to create a team."
            # Check if the Team already exists
            existing_team = await self.table_team.get_team_record(team_name=team_name)
            assert not existing_team, f"Team already exists."
            # Check if the Player is already on a Team
            player_id = await player.get_field(PlayerFields.record_id)
            existing_team = await self.table_team_player.get_team_player_records(
                player_id=player_id
            )
            assert not existing_team, f"You are already on a team."
            # Create the Team and Captain Records
            new_team = await self.table_team.create_team_record(team_name=team_name)
            assert new_team, f"Error: Could not create team."
            team_id = await new_team.get_field(TeamFields.record_id)
            team_player = await self.table_team_player.create_team_player_record(
                team_id=team_id,
                player_id=player_id,
                is_captain=True,
            )
            assert team_player, f"Error: Could not add team captain."
            # Update Discord roles
            discord_member = interaction.user
            region = await player.get_field(PlayerFields.region)
            await ManageTeamsHelpers.member_remove_team_roles(discord_member)
            await ManageTeamsHelpers.member_add_team_role(discord_member, team_name)
            await ManageTeamsHelpers.member_add_captain_role(discord_member, region)
            # Success
            message = f"Team created: '{team_name}'"
            return await interaction.followup.send(message)
        except AssertionError as message:
            await interaction.followup.send(message)
        except Exception as error:
            message = f"Error: Something went wrong."
            await interaction.followup.send(message)
            raise error

    async def add_player_to_team(
        self, interaction: discord.Interaction, player_name: str
    ):
        """Add a Player to a Team by name"""
        try:
            # This could take a while
            await interaction.response.defer()
            # Get info about the requestor
            requestor = await self.table_player.get_player_record(
                discord_id=interaction.user.id
            )
            assert requestor, f"You must be registered as a Player to add a Player."
            requestor_region = await requestor.get_field(PlayerFields.region)
            requestor_team_players = (
                await self.table_team_player.get_team_player_records(
                    player_id=await requestor.get_field(PlayerFields.record_id)
                )
            )
            assert requestor_team_players, f"You must be on a Team to add a Player."
            requestor_team_player = requestor_team_players[0]
            requestor_is_captain = False
            for captain_field in [
                TeamPlayerFields.is_captain,
                TeamPlayerFields.is_co_captain,
            ]:
                is_captain = await requestor_team_player.get_field(captain_field)
                requestor_is_captain = True if requestor_is_captain else is_captain
            assert requestor_is_captain, "You must be a team captain to add a Player."
            # Get info about the Team
            team_id = await requestor_team_player.get_field(TeamPlayerFields.team_id)
            team_players = await self.table_team_player.get_team_player_records(
                team_id=team_id
            )
            assert len(team_players) < constants.TEAM_PLAYERS_MAX, f"Team is full."
            team = await self.table_team.get_team_record(record_id=team_id)
            team_name = await team.get_field(TeamFields.team_name)
            # Get info about the Player
            player = await self.table_player.get_player_record(player_name=player_name)
            assert player, f"Player not found."
            player_name = await player.get_field(PlayerFields.player_name)
            player_region = await player.get_field(PlayerFields.region)
            assert player_region == requestor_region, f"Player must be in same region."
            player_id = await player.get_field(PlayerFields.record_id)
            existing_team_player = await self.table_team_player.get_team_player_records(
                player_id=player_id
            )
            assert not existing_team_player, f"Player is already on a team."
            # Add the Player to the Team
            new_team_player = await self.table_team_player.create_team_player_record(
                team_id=team_id,
                player_id=player_id,
            )
            assert new_team_player, f"Error: Could not add Player to Team."
            # Update Player's Discord roles
            player_discord_id = await player.get_field(PlayerFields.discord_id)
            player_discord_member = await discord_helpers.member_from_discord_id(
                guild=interaction.guild,
                discord_id=player_discord_id,
            )
            await ManageTeamsHelpers.member_remove_team_roles(player_discord_member)
            await ManageTeamsHelpers.member_add_team_role(
                player_discord_member, team_name
            )
            # Success
            message = f"Player '{player_name}' added to team '{team_name}'"
            return await interaction.followup.send(message)
        except AssertionError as message:
            await interaction.followup.send(message)
        except Exception as error:
            message = f"Error: Something went wrong."
            await interaction.followup.send(message)
            raise error

    async def accept_invite(self, interaction: discord.Interaction):
        """Add the requestor to their Team"""
        try:
            # This could take a while
            await interaction.response.defer()
            # Get info about the requestor
            requestor = await self.table_player.get_player_record(
                discord_id=interaction.user.id
            )
            assert requestor, f"You must be registered as a Player to accept an invite."
            requestor_id = await requestor.get_field(PlayerFields.record_id)
            requestor_team_players = (
                await self.table_team_player.get_team_player_records(
                    player_id=requestor_id
                )
            )
            assert not requestor_team_players, f"You are already on a team."
            # Get info about the Team
            team_id = await requestor.get_field(PlayerFields.invited_to_team_id)
            team = await self.table_team.get_team_record(record_id=team_id)
            team_name = await team.get_field(TeamFields.team_name)
            team_players = await self.table_team_player.get_team_player_records(
                team_id=team_id
            )
            assert len(team_players) < constants.TEAM_PLAYERS_MAX, f"Team is full."
            # Add the Player to the Team
            new_team_player = await self.table_team_player.create_team_player_record(
                team_id=team_id,
                player_id=requestor_id,
            )
            assert new_team_player, f"Error: Could not add Player to Team."
            # Update Player's Discord roles
            discord_member = interaction.user
            await ManageTeamsHelpers.member_remove_team_roles(discord_member)
            await ManageTeamsHelpers.member_add_team_role(discord_member, team_name)
            # Success
            message = f"You have joined Team '{team_name}'"
            return await interaction.followup.send(message)
        except AssertionError as message:
            await interaction.followup.send(message)
        except Exception as error:
            message = f"Error: Something went wrong."
            await interaction.followup.send(message)
            raise error

    async def remove_player_from_team(
        self, interaction: discord.Interaction, player_name: str
    ):
        """Remove a Player from a Team by name"""
        try:
            # This could take a while
            await interaction.response.defer()
            # Get info about the requestor
            requestor = await self.table_player.get_player_record(
                discord_id=interaction.user.id
            )
            assert requestor, f"You must registered to remove players"
            requestor_player_id = await requestor.get_field(PlayerFields.record_id)
            requestor_team_players = (
                await self.table_team_player.get_team_player_records(
                    player_id=requestor_player_id
                )
            )
            assert requestor_team_players, f"You must be on a team to remove players."
            requestor_team_player = requestor_team_players[0]
            requestor_is_captain = False
            for captain_field in [
                TeamPlayerFields.is_captain,
                TeamPlayerFields.is_co_captain,
            ]:
                is_captain = await requestor_team_player.get_field(captain_field)
                requestor_is_captain = True if requestor_is_captain else is_captain
            assert requestor_is_captain, "You must be a team captain to remove players."
            # Get info about the Team
            team_id = await requestor_team_player.get_field(TeamPlayerFields.team_id)
            team: TeamRecord = await self.table_team.get_team_record(record_id=team_id)
            team_name = await team.get_field(TeamFields.team_name)
            team_players = await self.table_team_player.get_team_player_records(
                team_id=team_id
            )
            # Get info about the Player
            player = await self.table_player.get_player_record(player_name=player_name)
            assert player, f"Player not found."
            player_name = await player.get_field(PlayerFields.player_name)
            player_id = await player.get_field(PlayerFields.record_id)
            player_team_player = None
            for team_player in team_players:
                if await team_player.get_field(TeamPlayerFields.player_id) == player_id:
                    player_team_player = team_player
            assert player_team_player, f"Player is not on the team."
            player_is_captain = await player_team_player.get_field(
                TeamPlayerFields.is_captain
            )
            assert not player_is_captain, f"Cannot remove the team captain"
            # Update Player's Discord roles
            player_discord_id = await player.get_field(PlayerFields.discord_id)
            player_discord_member = await discord_helpers.member_from_discord_id(
                guild=interaction.guild,
                discord_id=player_discord_id,
            )
            await ManageTeamsHelpers.member_remove_team_roles(player_discord_member)
            # Remove the Player from the Team
            await self.table_team_player.delete_team_player_record(player_team_player)
            # Success
            message = f"Player '{player_name}' removed from team '{team_name}'"
            return await interaction.followup.send(message)
        except AssertionError as message:
            await interaction.followup.send(message)
        except Exception as error:
            message = f"Error: Something went wrong."
            await interaction.followup.send(message)
            raise error

    async def promote_player_to_co_captain(
        self, interaction: discord.Interaction, player_name
    ):
        """Promote a Player to Team captain"""
        try:
            # This could take a while
            await interaction.response.defer()
            # Get info about the requestor
            requestor = await self.table_player.get_player_record(
                discord_id=interaction.user.id
            )
            assert requestor, f"You must be registered as a player to promote players."
            requestor_id = await requestor.get_field(PlayerFields.record_id)
            requestor_team_players = (
                await self.table_team_player.get_team_player_records(
                    player_id=requestor_id
                )
            )
            assert requestor_team_players, f"You must be on a team to promote players."
            requestor_team_player = requestor_team_players[0]
            requestor_is_captain = await requestor_team_player.get_field(
                TeamPlayerFields.is_captain
            )
            assert requestor_is_captain, f"You must be team captain to promote players."
            # Get info about the Team
            team_id = await requestor_team_player.get_field(TeamPlayerFields.team_id)
            team_players = await self.table_team_player.get_team_player_records(
                team_id=team_id
            )
            # Get info about co-captain
            co_captain_id = None
            for team_player in team_players:
                if await team_player.get_field(TeamPlayerFields.is_co_captain):
                    co_captain_id = await team_player.get_field(
                        TeamPlayerFields.player_id
                    )
            assert not co_captain_id, f"Team already has a co-captain."
            # Get info about the Player
            player = await self.table_player.get_player_record(player_name=player_name)
            assert player, f"Player not found."
            player_name = await player.get_field(PlayerFields.player_name)
            player_id = await player.get_field(PlayerFields.record_id)
            player_team_player = None
            for team_player in team_players:
                if await team_player.get_field(TeamPlayerFields.player_id) == player_id:
                    player_team_player = team_player
            assert player_team_player, f"Player is not on the team."
            assert player_id != requestor_id, f"Cannot promote yourself."
            # Update Player's TeamPlayer record
            await player_team_player.set_field(TeamPlayerFields.is_co_captain, True)
            await self.table_team_player.update_team_player_record(player_team_player)
            # Update Player's Discord roles
            region = await requestor.get_field(PlayerFields.region)
            player_discord_id = await player.get_field(PlayerFields.discord_id)
            player_discord_member = await discord_helpers.member_from_discord_id(
                guild=interaction.guild,
                discord_id=player_discord_id,
            )
            await ManageTeamsHelpers.member_add_captain_role(
                player_discord_member, region
            )
            # Success
            message = f"Player '{player_name}' promoted to co-captain"
            return await interaction.followup.send(message)
        except AssertionError as message:
            await interaction.followup.send(message)
        except Exception as error:
            message = f"Error: Something went wrong."
            await interaction.followup.send(message)
            raise error

    async def demote_player_from_co_captain(
        self, interaction: discord.Interaction, player_name
    ):
        """Demote a Player from Team captain"""
        try:
            # This could take a while
            await interaction.response.defer()
            # Get info about the requestor
            requestor = await self.table_player.get_player_record(
                discord_id=interaction.user.id
            )
            assert requestor, f"You must be registered as a player to demote players."
            requestor_id = await requestor.get_field(PlayerFields.record_id)
            requestor_team_players = (
                await self.table_team_player.get_team_player_records(
                    player_id=requestor_id
                )
            )
            assert requestor_team_players, f"You must be on a team to demote players."
            requestor_team_player = requestor_team_players[0]
            requestor_is_captain = await requestor_team_player.get_field(
                TeamPlayerFields.is_captain
            )
            assert requestor_is_captain, f"You must be team captain to demote players."
            # Get info about the Team
            team_id = await requestor_team_player.get_field(TeamPlayerFields.team_id)
            team_players = await self.table_team_player.get_team_player_records(
                team_id=team_id
            )
            # Get info about the Player
            player = await self.table_player.get_player_record(player_name=player_name)
            assert player, f"Player not found."
            player_name = await player.get_field(PlayerFields.player_name)
            player_id = await player.get_field(PlayerFields.record_id)
            player_team_player = None
            for team_player in team_players:
                if await team_player.get_field(TeamPlayerFields.player_id) == player_id:
                    player_team_player = team_player
            assert player_team_player, f"Player is not on the team."
            is_co_captain = await player_team_player.get_field(
                TeamPlayerFields.is_co_captain
            )
            assert is_co_captain, f"Player is not a co-captain."
            # Update Player's TeamPlayer record
            await player_team_player.set_field(TeamPlayerFields.is_co_captain, False)
            await self.table_team_player.update_team_player_record(player_team_player)
            # Update Player's Discord roles
            player_discord_id = await player.get_field(PlayerFields.discord_id)
            player_discord_member = await discord_helpers.member_from_discord_id(
                guild=interaction.guild,
                discord_id=player_discord_id,
            )
            await ManageTeamsHelpers.member_remove_captain_role(player_discord_member)
            # Success
            message = f"Player '{player_name}' demoted from co-captain"
            return await interaction.followup.send(message)
        except AssertionError as message:
            await interaction.followup.send(message)
        except Exception as error:
            message = f"Error: Something went wrong."
            await interaction.followup.send(message)
            raise error

    async def leave_team(self, interaction: discord.Interaction):
        """Remove the requestor from their Team"""
        try:
            # This could take a while
            await interaction.response.defer()
            # Get info about the requestor
            requestor = await self.table_player.get_player_record(
                discord_id=interaction.user.id
            )
            assert requestor, f"You must be registered as a Player to leave a Team."
            requestor_player_id = await requestor.get_field(PlayerFields.record_id)
            requestor_team_players = (
                await self.table_team_player.get_team_player_records(
                    player_id=requestor_player_id
                )
            )
            assert requestor_team_players, f"You must be on a team to leave."
            requestor_team_player = requestor_team_players[0]
            requestor_is_captain = await requestor_team_player.get_field(
                TeamPlayerFields.is_captain
            )
            # Get info about the Team
            team_id = await requestor_team_player.get_field(TeamPlayerFields.team_id)
            team = await self.table_team.get_team_record(record_id=team_id)
            team_name = await team.get_field(TeamFields.team_name)
            team_players = await self.table_team_player.get_team_player_records(
                team_id=team_id
            )
            if requestor_is_captain:
                # Get info about the co-captain
                co_captain_team_player = None
                for team_player in team_players:
                    if await team_player.get_field(TeamPlayerFields.is_co_captain):
                        co_captain_team_player = team_player
                assert (
                    co_captain_team_player
                ), f"Captain must promote a co-captain before leaving."
                # promote the co-captain to captain
                co_cap = co_captain_team_player
                await co_cap.set_field(TeamPlayerFields.is_captain, True)
                await co_cap.set_field(TeamPlayerFields.is_co_captain, False)
                await self.table_team_player.update_team_player_record(co_cap)
            # Remove the Player from the Team
            await self.table_team_player.delete_team_player_record(
                requestor_team_player
            )
            # Update Player's Discord roles
            member = interaction.user
            await ManageTeamsHelpers.member_remove_team_roles(member)
            # Success
            message = f"You have left Team '{team_name}'"
            return await interaction.followup.send(message)
        except AssertionError as message:
            await interaction.followup.send(message)
        except Exception as error:
            message = f"Error: Something went wrong."
            await interaction.followup.send(message)
            raise error

    async def disband_team(self, interaction: discord.Interaction):
        """Disband the requestor's Team"""
        try:
            # This could take a while
            await interaction.response.defer()
            # Get info about the requestor
            requestor = await self.table_player.get_player_record(
                discord_id=interaction.user.id
            )
            assert requestor, f"You must be registered as a player to disband a team."
            requestor_id = await requestor.get_field(PlayerFields.record_id)
            requestor_team_players = (
                await self.table_team_player.get_team_player_records(
                    player_id=requestor_id
                )
            )
            assert requestor_team_players, f"You must be on a team to disband it."
            requestor_team_player = requestor_team_players[0]
            requestor_is_captain = await requestor_team_player.get_field(
                TeamPlayerFields.is_captain
            )
            assert requestor_is_captain, f"You must be team captain to disband a team."
            # Get info about the Team
            team_id = await requestor_team_player.get_field(TeamPlayerFields.team_id)
            team = await self.table_team.get_team_record(record_id=team_id)
            team_name = await team.get_field(TeamFields.team_name)
            team_players = await self.table_team_player.get_team_player_records(
                team_id=team_id
            )
            # Remove all Players from the Team
            for team_player in team_players:
                # Remove Player's Discord roles
                player_id = await team_player.get_field(TeamPlayerFields.player_id)
                player = await self.table_player.get_player_record(record_id=player_id)
                player_discord_id = await player.get_field(PlayerFields.discord_id)
                player_discord_member = await discord_helpers.member_from_discord_id(
                    guild=interaction.guild,
                    discord_id=player_discord_id,
                )
                await ManageTeamsHelpers.member_remove_team_roles(player_discord_member)
                # Remove the Player from the Team
                await self.table_team_player.delete_team_player_record(team_player)
            # Delete the Team
            await self.table_team.delete_team_record(team)
            # Success
            message = f"Team '{team_name}' has been disbanded"
            return await interaction.followup.send(message)
        except AssertionError as message:
            await interaction.followup.send(message)
        except Exception as error:
            message = f"Error: Something went wrong."
            await interaction.followup.send(message)
            raise error

    async def get_team_details(self, interaction: discord.Interaction, team_name: str):
        """Get a Team by name"""
        try:
            # This could take a while
            await interaction.response.defer()
            # Get info about the Team
            team = await self.table_team.get_team_record(team_name=team_name)
            assert team, f"Team not found."
            team_name = await team.get_field(TeamFields.team_name)
            team_id = await team.get_field(TeamFields.record_id)
            team_players = await self.table_team_player.get_team_player_records(
                team_id=team_id
            )
            # Get info about the Players
            captain_name = None
            co_captain_name = None
            player_names = []
            for team_player in team_players:
                player_id = await team_player.get_field(TeamPlayerFields.player_id)
                player = await self.table_player.get_player_record(record_id=player_id)
                player_name = await player.get_field(PlayerFields.player_name)
                player_names.append(player_name)
                if await team_player.get_field(TeamPlayerFields.is_captain):
                    captain_name = player_name
                elif await team_player.get_field(TeamPlayerFields.is_co_captain):
                    co_captain_name = player_name
            player_names.sort()
            # Format the message
            message_dict = {
                "team": team_name,
                "captain": captain_name,
                "co_captain": co_captain_name,
                "players": player_names,
            }
            message = await bot_helpers.format_json(message_dict)
            message = await discord_helpers.code_block(message, language="json")
            return await interaction.followup.send(message)
        except AssertionError as message:
            await interaction.followup.send(message)
        except Exception as error:
            message = f"Error: Something went wrong."
            await interaction.followup.send(message)
            raise error


class ManageTeamsHelpers:
    """EML Team Management Helpers"""

    ### DISCORD ###

    @staticmethod
    async def member_remove_team_roles(member: discord.Member):
        """Remove all Team roles from a Guild Member"""
        prefixes = [constants.ROLE_PREFIX_TEAM, constants.ROLE_PREFIX_CAPTAIN]
        for role in member.roles:
            if any(role.name.startswith(prefix) for prefix in prefixes):
                await member.remove_roles(role)
        return True

    @staticmethod
    async def member_add_team_role(member: discord.Member, team_name: str):
        """Add a Team role to a Guild Member"""
        role_name = f"{constants.ROLE_PREFIX_TEAM}{team_name}"
        role = await discord_helpers.guild_role_get_or_create(member.guild, role_name)
        await member.add_roles(role)
        return True

    @staticmethod
    async def member_add_captain_role(member: discord.Member, region: str):
        """Add a Captain role to a Guild Member"""
        role_name = f"{constants.ROLE_PREFIX_CAPTAIN}{region}"
        role = await discord_helpers.guild_role_get_or_create(member.guild, role_name)
        await member.add_roles(role)
        return True

    @staticmethod
    async def member_remove_captain_role(member: discord.Member):
        """Remove a Captain role from a Guild Member"""
        prefixes = [constants.ROLE_PREFIX_CAPTAIN]
        for role in member.roles:
            if any(role.name.startswith(prefix) for prefix in prefixes):
                await member.remove_roles(role)
        return True
