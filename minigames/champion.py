# Copyright (c) 2011-2020 Eric Froemling
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
# -----------------------------------------------------------------------------
"""Elimination mini-game."""

# ba_meta require api 6
# (see https://ballistica.net/wiki/meta-tag-system)

#mod_version=1.01

from __future__ import annotations

from typing import TYPE_CHECKING

import ba
from bastd.actor.spazfactory import SpazFactory
from bastd.actor.scoreboard import Scoreboard

if TYPE_CHECKING:
	from typing import (Any, Tuple, Dict, Type, List, Sequence, Optional,
						Union)






class Player(ba.Player['Team']):
	"""Our player type for this game."""

	def __init__(self) -> None:
		self.lives = 0

class Team(ba.Team[Player]):
	"""Our team type for this game."""

	def __init__(self) -> None:
		self.survival_seconds: Optional[int] = None
		self.spawn_order: List[Player] = []



# ba_meta export game
class ChampionGame(ba.TeamGameActivity[Player, Team]):
	"""Game type where last player(s) left alive win."""

	name = 'Champion'
	description = 'Eliminate others and become the Champion.'
	scoreconfig = ba.ScoreConfig(label='Wins',
								 scoretype=ba.ScoreType.POINTS,
								 none_is_winner=True)
	# Show messages when players die since it's meaningful here.
	announce_player_deaths = True

	@classmethod
	def get_available_settings(
			cls, sessiontype: Type[ba.Session]) -> List[ba.Setting]:
		settings = [
			ba.IntChoiceSetting(
				'Time Limit',
				choices=[
					('None', 0),
					('1 Minute', 60),
					('2 Minutes', 120),
					('5 Minutes', 300),
					('10 Minutes', 600),
					('20 Minutes', 1200),
				],
				default=0,
			),
			ba.BoolSetting('Epic Mode', default=False),
		]
		return settings

	@classmethod
	def supports_session_type(cls, sessiontype: Type[ba.Session]) -> bool:
		return (issubclass(sessiontype, ba.FreeForAllSession))

	@classmethod
	def get_supported_maps(cls, sessiontype: Type[ba.Session]) -> List[str]:
		
		return ba.getmaps('melee')

	def __init__(self, settings: dict):
		super().__init__(settings)
		self.roundNames=['Grand Finale','Semi-Final','Quarter Final','Pre Quarter-Final']
		
		self._scoreboard = Scoreboard()
		self._start_time: Optional[float] = None
		self._vs_text: Optional[ba.Actor] = None
		self._round_end_timer: Optional[ba.Timer] = None
		self.count=0
		self.myPlayers=None
		self.myPlayersScore=None
		self._epic_mode = bool(settings['Epic Mode'])
		self._lives_per_player = 1
		self._time_limit = float(settings['Time Limit'])
		self._balance_total_lives = bool(
			settings.get('Balance Total Lives', False))
		self.versusNode=None
		self.roundNameNode=None
		self.playersInGameNode=None
		self.upNextNode=None
		# Base class OVERrides:
		self.slow_motion = self._epic_mode
		self.default_music = (ba.MusicType.EPIC
							  if self._epic_mode else ba.MusicType.SURVIVAL)

	def get_instance_description(self) -> Union[str, Sequence]:
		return 'Eliminate others and become the Champion.[AbhinaYx-ModSquad]'

	def get_instance_description_short(self) -> Union[str, Sequence]:
		return 'eliminate others and become the Champion.'
	def on_player_join(self, player: Player) -> None:

		# No longer allowing mid-game joiners here; too easy to exploit.
		if self.has_begun():

			# Make sure their team has survival seconds set if they're all dead
			# (otherwise blocked new ffa players are considered 'still alive'
			# in score tallying).
			if (self._get_total_team_lives(player.team) == 0
					and player.team.survival_seconds is None):
				player.team.survival_seconds = 0
			ba.screenmessage(
				ba.Lstr(resource='playerDelayedJoinText',
						subs=[('${PLAYER}', player.getname(full=True))]),
				color=(0, 1, 0),
			)
			return

		player.lives = self._lives_per_player


		# Don't waste time doing this until begin.


	def on_begin(self) -> None:

		#===
		self.myPlayers=[str(x.getname()) for x in self.players]
		self.myPlayersScore=[0 for x in self.myPlayers]
		for x in self.teams:x.survival_seconds=0
		self.spawnPlayer()
		
		#===
		super().on_begin()
		self._start_time = ba.time()
		self.setup_standard_time_limit(self._time_limit)
		self.setup_standard_powerup_drops()
		

		# We could check game-over conditions at explicit trigger points,
		# but lets just do the simple thing and poll it.
		ba.timer(1.0, self._update, repeat=True)


	def _get_spawn_point(self, player: Player) -> Optional[ba.Vec3]:
		del player  # Unused.
		return None

	def spawn_player(self, player: Player) -> ba.Actor:
		actor = self.spawn_player_spaz(player, self._get_spawn_point(player))
		ba.timer(0.3, ba.Call(self._print_lives, player))

		return actor

	def _print_lives(self, player: Player) -> None:
		from bastd.actor import popuptext

		# We get called in a timer so it's possible our player has left/etc.
		if not player or not player.is_alive() or not player.node:
			return

		popuptext.PopupText('x' + str(player.lives - 1),
							color=(1, 1, 0, 1),
							offset=(0, -0.8, 0),
							random_offset=0.0,
							scale=1.8,
							position=player.node.position).autoretain()

	def on_player_leave(self, player: Player) -> None:
		super().on_player_leave(player)
		# Remove us from spawn-order.
		
		# Update icons in a moment since our team will be gone from the
		# list then.
		#==
		if player.getname() in self.myPlayers:
			self.playerInGameNodeFunc()
			
			if player.is_alive():
				if self.myPlayers[self.count-2]==str(player.getname()):
					winningPlayer= self.playerFromName(self.myPlayers[self.count-1])
				else:
					winningPlayer= self.playerFromName(self.myPlayers[self.count-2])


				if winningPlayer:
					winningPlayer.team.survival_seconds+=1
					if winningPlayer.is_alive():
						winningPlayer.actor.handlemessage(ba.DieMessage(immediate=True))
			
			if self.myPlayers.index(player.getname())<self.count:self.count-=1
			self.myPlayers.remove(str(player.getname()))
			if player.is_alive():self.spawnPlayer()
			else:
				if len(self.myPlayers)>2:self.upNextNodeFunc()
				if len(self.myPlayers)==2:
					if self.upNextNode:self.upNextNode.delete()
		#==
			

	def _get_total_team_lives(self, team: Team) -> int:
		return sum(player.lives for player in team.players)

	def handlemessage(self, msg: Any) -> Any:

		if isinstance(msg, ba.PlayerDiedMessage):
			#==
			losingPlayer=msg.getplayer(Player)
			if len(self.myPlayers)>1:
				if self.playerFromName(self.myPlayers[self.count-2])==losingPlayer:
					winningPlayer= self.playerFromName(self.myPlayers[self.count-1])
				else:
					winningPlayer= self.playerFromName(self.myPlayers[self.count-2])
				if str(losingPlayer.getname()) in self.myPlayers:self.myPlayers.remove(str(losingPlayer.getname()))
				winningPlayer.team.survival_seconds+=1
				if winningPlayer.is_alive() and not len(self.myPlayers)==1:
					winningPlayer.actor.handlemessage(ba.DieMessage(immediate=True))
				self.count-=1
				self.spawnPlayer()
			#==

			# Augment standard behavior.
			super().handlemessage(msg)
			
			player: Player = msg.getplayer(Player)

			player.lives -= 1
			if player.lives < 0:
				ba.print_error("Got lives < 0 in Elim; this shouldn't happen.")
				player.lives = 0

			# If we have any icons, update their state.

			# Play big death sound on our last death
			# or for every one in solo mode.
			if player.lives == 0:
				ba.playsound(SpazFactory.get().single_player_death_sound)

			# If we hit zero lives, we're dead (and our team might be too).
			if player.lives == 0:
				pass
			else:
				self.respawn_player(player)



	def _update(self) -> None:

		# If we're down to 1 or fewer living teams, start a timer to end
		# the game (allows the dust to settle and draws to occur if deaths
		# are close enough).
		if len(self.players)<=1 or len(self.myPlayers)<=1:
			self.playerInGameNodeFunc()
			self._round_end_timer = ba.Timer(0.5, self.end_game)

	def _get_living_teams(self) -> List[Team]:
		return [
			team for team in self.teams
			if len(team.players) > 0 and any(player.lives > 0
											 for player in team.players)
		]

	def end_game(self) -> None:
		if self.has_ended():
			return
		results = ba.GameResults()
		
		self._vs_text = None  # Kill our 'vs' if its there.
		for team in self.teams:
			results.set_team_score(team, team.survival_seconds)
		self.end(results=results)
		if not results.winning_sessionteam:self.announce_game_results(results=results,activity=ba.getactivity())



#===
	def roundNameFunc(self,totalPlayers=-1):
		two=2
		roundNameInt=0
		if totalPlayers==-1:totalPlayers=len(self.myPlayers)
		while True:
			if totalPlayers<=two:
				break
			else:
				two*=2
				roundNameInt+=1
		return roundNameInt
	def playerFromName(self, name):
		for x in self.players:
			if str(x.getname())==name:
				return x

	def playerInGameNodeFunc(self):
		if self.playersInGameNode:self.playersInGameNode.delete()


		playersInGameText="Players In-Game:\n"
		for i in self.myPlayers:
			y=self.playerFromName(i)
			if y:
				playersInGameText+=i
				x=y.team.survival_seconds
				playersInGameText+=' (W:'+str(x)+')\n'

		self.playersInGameNode=ba.newnode('text',
					attrs={
						'v_attach': 'top',
						'h_attach': 'left',
						'color': (1, 1, 1, 0.5),
						'flatness': 0.5,
						'shadow': 0.5,
						'position': (17, -84),
						'scale': 0.7,
						'maxwidth':480,
						'text': playersInGameText
					}
		)
	def upNextNodeFunc(self):
		if self.upNextNode:self.upNextNode.delete()
		playerPlayingRightNow1=self.myPlayers[self.count-2]
		playerPlayingRightNow2=self.myPlayers[self.count-1]
		upNextP1='TBD'
		upNextP2='TBD'
		n=len(self.myPlayers)
		if self.count>=n-1:
			upNextP1=self.myPlayers[0]
			upNextP2=self.myPlayers[1]
		else:
			upNextP1=self.myPlayers[self.count]
			upNextP2=self.myPlayers[self.count+1]
		
		if upNextP1 in [playerPlayingRightNow1,playerPlayingRightNow2]:upNextP1="TBD"
		if upNextP2 in [playerPlayingRightNow1,playerPlayingRightNow2]:upNextP2="TBD"
		upNextNodeText="Up Next:\n"+upNextP1+" vs "+upNextP2+"\n"
		z=self.roundNameFunc(n-1)
		if z<4:upNextNodeText+=self.roundNames[z]
		self.upNextNode=ba.newnode('text',
				attrs={
							'v_attach': 'top',
							'h_attach': 'right',
							'h_align':'right',
							'color': (1, 1, 1, 0.5),
							'flatness': 0.5,
							'shadow': 0.5,
							'position': (-17, -60),
							'scale': 0.7,
							'maxwidth':480,
							'text': upNextNodeText
						}
					)
			
	def spawnPlayer(self):
		n=len(self.myPlayers)
		if n==1:return
		if self.count>=n-1 and n>=2:
			self.count=0

		if self.versusNode:self.versusNode.delete()
		if self.roundNameNode:self.roundNameNode.delete()
		
		playerToSpawn1=self.playerFromName(self.myPlayers[self.count])
		
		
			
		
		self.spawn_player(playerToSpawn1)

		self.count+=1
		playerToSpawn2=self.playerFromName(self.myPlayers[self.count])
		
		self.spawn_player(playerToSpawn2)
		self.count+=1
		self.playerInGameNodeFunc()
		if n>2:

			self.upNextNodeFunc()
		if n==2:
			if self.upNextNode:self.upNextNode.delete()
		self.versusNode=ba.newnode('text',
						attrs={
							'v_attach': 'top',
							'h_attach': 'center',
							'h_align': 'center',
							'color': (1, 1, 1, 0.5),
							'flatness': 0.5,
							'shadow': 0.5,
							'position': (0, -70),
							'scale': 1,
							'text': str(playerToSpawn1.getname())+" vs "+str(playerToSpawn2.getname())
						}
			)
		roundNameInt=self.roundNameFunc()
		if roundNameInt<4:
			self.roundNameNode=ba.newnode('text',
						attrs={
							'v_attach': 'top',
							'h_attach': 'center',
							'h_align': 'center',
							'color': (1, 1, 1, 0.5),
							'flatness': 0.5,
							'shadow': 0.5,
							'position': (0, -100),
							'scale': 1,
							'text': self.roundNames[roundNameInt]
						}
			)
	def announce_game_results(self,results: ba.GameResults,activity: ba.GameActivity) -> None:
		import _ba
		from ba._math import normalized_color
		from ba._general import Call
		from ba._gameutils import cameraflash
		from ba._lang import Lstr
		from ba._freeforallsession import FreeForAllSession
		from ba._messages import CelebrateMessage
		_ba.timer(2.1, Call(_ba.playsound, _ba.getsound('boxingBell')))

		celebrate_msg = CelebrateMessage(duration=10.0)
		player=self.playerFromName(self.myPlayers[0])
		player.actor.handlemessage(celebrate_msg)
		cameraflash()

				# Some languages say "FOO WINS" different for teams vs players.
		if isinstance(self, FreeForAllSession):
			wins_resource = 'winsPlayerText'
		else:
			wins_resource = 'winsTeamText'
		wins_text = Lstr(resource=wins_resource,
						subs=[('${NAME}', player.team.name)])
		activity.show_zoom_message(
			wins_text,
			scale=0.85,
			color=normalized_color(player.team.color),
		)
