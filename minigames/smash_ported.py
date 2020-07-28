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

from __future__ import annotations
from ba._dualteamsession import DualTeamSession
import _ba
import random
from ba._messages import PlayerDiedMessage, StandMessage
from ba import _math
from ba._gameutils import animate
from ba._coopsession import CoopSession
from bastd.actor.playerspaz import PlayerSpaz,PlayerSpazHurtMessage
from typing import TYPE_CHECKING
from bastd.actor.bomb import Blast,Bomb
import ba
from bastd.actor.spazfactory import SpazFactory
from bastd.actor.scoreboard import Scoreboard
if TYPE_CHECKING:
    from typing import (Any, Tuple, Dict, Type, List, Sequence, Optional,
                        Union)

class PowBox(Bomb):
    def __init__(self, position=(0, 1, 0), velocity=(0, 0, 0)):
        super().__init__(position, velocity,
                        bomb_type='tnt', blast_radius=2.5,
                        source_player=None, owner=None)
        self._powText=None
        self.setPowText()


    def setPowText(self, color=(1, 1, 0.4)):
        m = ba.newnode('math', owner=self.node, attrs={'input1': (0, 0.7, 0), 'operation': 'add'})
        self.node.connectattr('position', m, 'input2')
        self._powText = ba.newnode('text',
                                      owner=self.node,
                                      attrs={'text':'POW!',
                                             'in_world':True,
                                             'shadow':1.0,
                                             'flatness':1.0,
                                             'color':color,
                                             'scale':0.0,
                                             'h_align':'center'})
        m.connectattr('output', self._powText, 'position')
        ba.animate(self._powText, 'scale', {0: 0.0, 1: 0.01})

    def handlemessage(self, m):

        if isinstance(m, ba.PickedUpMessage):
            self._heldBy = m.node
        elif isinstance(m, ba.DroppedMessage):
            ba.WeakCall(self.anim)
            ba.timer(0.6, ba.WeakCall(self.pow))
        super().handlemessage(m)
    def anim(self):
        ba.animate(self._powText, 'scale', {0:0.01, 0.6: 0.03})
    def pow(self):
        self.explode()

class Icon(ba.Actor):
    """Creates in in-game icon on screen."""

    def __init__(self,
                 player: Player,
                 position: Tuple[float, float],
                 scale: float,
                 show_lives: bool = True,
                 show_death: bool = True,
                 name_scale: float = 1.0,
                 name_maxwidth: float = 115.0,
                 flatness: float = 1.0,
                 shadow: float = 1.0):
        super().__init__()

        self._player = player
        self._show_lives = show_lives
        self._show_death = show_death
        self._name_scale = name_scale
        self._outline_tex = ba.gettexture('characterIconMask')

        icon = player.get_icon()
        self.node = ba.newnode('image',
                               delegate=self,
                               attrs={
                                   'texture': icon['texture'],
                                   'tint_texture': icon['tint_texture'],
                                   'tint_color': icon['tint_color'],
                                   'vr_depth': 400,
                                   'tint2_color': icon['tint2_color'],
                                   'mask_texture': self._outline_tex,
                                   'opacity': 1.0,
                                   'absolute_scale': True,
                                   'attach': 'bottomCenter'
                               })
        self._name_text = ba.newnode(
            'text',
            owner=self.node,
            attrs={
                'text': ba.Lstr(value=player.getname()),
                'color': ba.safecolor(player.team.color),
                'h_align': 'center',
                'v_align': 'center',
                'vr_depth': 410,
                'maxwidth': name_maxwidth,
                'shadow': shadow,
                'flatness': flatness,
                'h_attach': 'center',
                'v_attach': 'bottom'
            })
        if self._show_lives:
            self._lives_text = ba.newnode('text',
                                          owner=self.node,
                                          attrs={
                                              'text': 'x0',
                                              'color': (1, 1, 0.5),
                                              'h_align': 'left',
                                              'vr_depth': 430,
                                              'shadow': 1.0,
                                              'flatness': 1.0,
                                              'h_attach': 'center',
                                              'v_attach': 'bottom'
                                          })
        self.set_position_and_scale(position, scale)

    def set_position_and_scale(self, position: Tuple[float, float],
                               scale: float) -> None:
        """(Re)position the icon."""
        assert self.node
        self.node.position = position
        self.node.scale = [70.0 * scale]
        self._name_text.position = (position[0], position[1] + scale * 52.0)
        self._name_text.scale = 1.0 * scale * self._name_scale
        if self._show_lives:
            self._lives_text.position = (position[0] + scale * 10.0,
                                         position[1] - scale * 43.0)
            self._lives_text.scale = 1.0 * scale

    def update_for_lives(self) -> None:
        """Update for the target player's current lives."""
        if self._player:
            lives = self._player.lives
        else:
            lives = 0
        if self._show_lives:
            if lives > 0:
                self._lives_text.text = 'x' + str(lives - 1)
            else:
                self._lives_text.text = ''
        if lives == 0:
            self._name_text.opacity = 0.2
            assert self.node
            self.node.color = (0.7, 0.3, 0.3)
            self.node.opacity = 0.2

    def handle_player_spawned(self) -> None:
        """Our player spawned; hooray!"""
        if not self.node:
            return
        self.node.opacity = 1.0
        self.update_for_lives()

    def handle_player_died(self) -> None:
        """Well poo; our player died."""
        if not self.node:
            return
        if self._show_death:
            ba.animate(
                self.node, 'opacity', {
                    0.00: 1.0,
                    0.05: 0.0,
                    0.10: 1.0,
                    0.15: 0.0,
                    0.20: 1.0,
                    0.25: 0.0,
                    0.30: 1.0,
                    0.35: 0.0,
                    0.40: 1.0,
                    0.45: 0.0,
                    0.50: 1.0,
                    0.55: 0.2
                })
            lives = self._player.lives
            if lives == 0:
                ba.timer(0.6, self.update_for_lives)

    def handlemessage(self, msg: Any) -> Any:
        if isinstance(msg, ba.DieMessage):
            self.node.delete()
            return None
        return super().handlemessage(msg)

class Player(ba.Player['Team']):
    """Our player type for this game."""

    def __init__(self) -> None:
        self.lives = 0
        self.icons: List[Icon] = []


class Team(ba.Team[Player]):
    """Our team type for this game."""

    def __init__(self) -> None:
        self.survival_seconds: Optional[int] = None
        self.spawn_order: List[Player] = []
class MyPlayerSpaz(PlayerSpaz):
    multiplyer=1
    def handlemessage(self,msg):

        if isinstance(msg, ba.HitMessage):
            if not self.node:
                return None
            if self.node.invincible:
                ba.playsound(SpazFactory.get().block_sound,
                             1.0,
                             position=self.node.position)
                return True

            # If we were recently hit, don't count this as another.
            # (so punch flurries and bomb pileups essentially count as 1 hit)
            local_time = ba.time(timeformat=ba.TimeFormat.MILLISECONDS)
            assert isinstance(local_time, int)
            if (self._last_hit_time is None
                    or local_time - self._last_hit_time > 1000):
                self._num_times_hit += 1
                self._last_hit_time = local_time

            mag = msg.magnitude * self.impact_scale

            velocity_mag = msg.velocity_magnitude * self.impact_scale
            damage_scale = 0.22

            # If they've got a shield, deliver it to that instead.
            if self.shield:
                if msg.flat_damage:
                    damage = msg.flat_damage * self.impact_scale
                else:
                    # Hit our spaz with an impulse but tell it to only return
                    # theoretical damage; not apply the impulse.
                    assert msg.force_direction is not None
                    self.node.handlemessage(
                        'impulse', msg.pos[0], msg.pos[1], msg.pos[2],
                        msg.velocity[0], msg.velocity[1], msg.velocity[2], mag,
                        velocity_mag, msg.radius, 1, msg.force_direction[0],
                        msg.force_direction[1], msg.force_direction[2])
                    damage = damage_scale * self.node.damage

                assert self.shield_hitpoints is not None
                self.shield_hitpoints -= int(damage)
                self.shield.hurt = (
                    1.0 -
                    float(self.shield_hitpoints) / self.shield_hitpoints_max)

                # Its a cleaner event if a hit just kills the shield
                # without damaging the player.
                # However, massive damage events should still be able to
                # damage the player. This hopefully gives us a happy medium.
                max_spillover = SpazFactory.get().max_shield_spillover_damage
                if self.shield_hitpoints <= 0:

                    # FIXME: Transition out perhaps?
                    self.shield.delete()
                    self.shield = None
                    ba.playsound(SpazFactory.get().shield_down_sound,
                                 1.0,
                                 position=self.node.position)

                    # Emit some cool looking sparks when the shield dies.
                    npos = self.node.position
                    ba.emitfx(position=(npos[0], npos[1] + 0.9, npos[2]),
                              velocity=self.node.velocity,
                              count=random.randrange(20, 30),
                              scale=1.0,
                              spread=0.6,
                              chunk_type='spark')

                else:
                    ba.playsound(SpazFactory.get().shield_hit_sound,
                                 0.5,
                                 position=self.node.position)

                # Emit some cool looking sparks on shield hit.
                assert msg.force_direction is not None
                ba.emitfx(position=msg.pos,
                          velocity=(msg.force_direction[0] * 1.0,
                                    msg.force_direction[1] * 1.0,
                                    msg.force_direction[2] * 1.0),
                          count=min(30, 5 + int(damage * 0.005)),
                          scale=0.5,
                          spread=0.3,
                          chunk_type='spark')

                # If they passed our spillover threshold,
                # pass damage along to spaz.
                if self.shield_hitpoints <= -max_spillover:
                    leftover_damage = -max_spillover - self.shield_hitpoints
                    shield_leftover_ratio = leftover_damage / damage

                    # Scale down the magnitudes applied to spaz accordingly.
                    mag *= shield_leftover_ratio
                    velocity_mag *= shield_leftover_ratio
                else:
                    return True  # Good job shield!
            else:
                shield_leftover_ratio = 1.0

            if msg.flat_damage:
                damage = int(msg.flat_damage * self.impact_scale *
                             shield_leftover_ratio)

            else:
                # Hit it with an impulse and get the resulting damage.
                assert msg.force_direction is not None
                if self.multiplyer > 3.0:
                    # at about 8.0 the physics glitch out
                    velocity_mag *= min((3.0 + (self.multiplyer-3.0)/4), 7.5) ** 1.9
                else:
                    velocity_mag *= self.multiplyer ** 1.9
                self.node.handlemessage(
                    'impulse', msg.pos[0], msg.pos[1], msg.pos[2],
                    msg.velocity[0], msg.velocity[1], msg.velocity[2], mag,
                    velocity_mag, msg.radius, 0, msg.force_direction[0],
                    msg.force_direction[1], msg.force_direction[2])

                damage = int(damage_scale * self.node.damage)
            self.node.handlemessage('hurt_sound')
            # Play punch impact sound based on damage if it was a punch.
            if msg.hit_type == 'punch':
                self.on_punched(damage)

                # If damage was significant, lets show it.
                if damage > 350:
                    assert msg.force_direction is not None
                    ba.show_damage_count('-' + str(int(damage / 10)) + '%',
                                         msg.pos, msg.force_direction)

                # Let's always add in a super-punch sound with boxing
                # gloves just to differentiate them.
                if msg.hit_subtype == 'super_punch':
                    ba.playsound(SpazFactory.get().punch_sound_stronger,
                                 1.0,
                                 position=self.node.position)
                if damage > 500:
                    sounds = SpazFactory.get().punch_sound_strong
                    sound = sounds[random.randrange(len(sounds))]
                else:
                    sound = SpazFactory.get().punch_sound
                ba.playsound(sound, 1.0, position=self.node.position)

                # Throw up some chunks.
                assert msg.force_direction is not None
                ba.emitfx(position=msg.pos,
                          velocity=(msg.force_direction[0] * 0.5,
                                    msg.force_direction[1] * 0.5,
                                    msg.force_direction[2] * 0.5),
                          count=min(10, 1 + int(damage * 0.0025)),
                          scale=0.3,
                          spread=0.03)

                ba.emitfx(position=msg.pos,
                          chunk_type='sweat',
                          velocity=(msg.force_direction[0] * 1.3,
                                    msg.force_direction[1] * 1.3 + 5.0,
                                    msg.force_direction[2] * 1.3),
                          count=min(30, 1 + int(damage * 0.04)),
                          scale=0.9,
                          spread=0.28)

                # Momentary flash.
                hurtiness = damage * 0.003
                punchpos = (msg.pos[0] + msg.force_direction[0] * 0.02,
                            msg.pos[1] + msg.force_direction[1] * 0.02,
                            msg.pos[2] + msg.force_direction[2] * 0.02)
                flash_color = (1.0, 0.8, 0.4)
                light = ba.newnode(
                    'light',
                    attrs={
                        'position': punchpos,
                        'radius': 0.12 + hurtiness * 0.12,
                        'intensity': 0.3 * (1.0 + 1.0 * hurtiness),
                        'height_attenuated': False,
                        'color': flash_color
                    })
                ba.timer(0.06, light.delete)

                flash = ba.newnode('flash',
                                   attrs={
                                       'position': punchpos,
                                       'size': 0.17 + 0.17 * hurtiness,
                                       'color': flash_color
                                   })
                ba.timer(0.06, flash.delete)

            if msg.hit_type == 'impact':
                assert msg.force_direction is not None
                ba.emitfx(position=msg.pos,
                          velocity=(msg.force_direction[0] * 2.0,
                                    msg.force_direction[1] * 2.0,
                                    msg.force_direction[2] * 2.0),
                          count=min(10, 1 + int(damage * 0.01)),
                          scale=0.4,
                          spread=0.1)
            if self.hitpoints > 0:
                self.multiplyer += min(damage / 2000, 0.15)
                self.set_score_text(str(int((self.multiplyer-1)*100))+"%")
                # It's kinda crappy to die from impacts, so lets reduce
                # impact damage by a reasonable amount *if* it'll keep us alive
                if msg.hit_type == 'impact' and damage > self.hitpoints:
                    # Drop damage to whatever puts us at 10 hit points,
                    # or 200 less than it used to be whichever is greater
                    # (so it *can* still kill us if its high enough)
                    newdamage = max(damage - 200, self.hitpoints - 10)
                    damage = newdamage
                self.node.handlemessage('flash')

                # If we're holding something, drop it.
                if damage > 0.0 and self.node.hold_node:
                    self.node.hold_node = None
                # self.hitpoints -= damage
                self.node.hurt = 1.0 - float(
                    self.hitpoints) / self.hitpoints_max

                # If we're cursed, *any* damage blows us up.
                if self._cursed and damage > 0:
                    ba.timer(
                        0.05,
                        ba.WeakCall(self.curse_explode,
                                    msg.get_source_player(ba.Player)))

                # If we're frozen, shatter.. otherwise die if we hit zero
                if self.frozen and (damage > 200 or self.hitpoints <= 0):
                    self.shatter()
                elif self.hitpoints <= 0:
                    self.node.handlemessage(
                        ba.DieMessage(how=ba.DeathType.IMPACT))

            # If we're dead, take a look at the smoothed damage value
            # (which gives us a smoothed average of recent damage) and shatter
            # us if its grown high enough.
            if self.hitpoints <= 0:
                damage_avg = self.node.damage_smoothed * damage_scale
                if damage_avg > 1000:
                    self.shatter()
            return None
        elif isinstance(msg, ba.PowerupMessage):
            if msg.poweruptype == 'health':
                if self.multiplyer > 2:
                    self.multiplyer *= 0.5
                else:
                    self.multiplyer *= 0.75
                self.multiplyer = max(1, self.multiplyer)
                self.set_score_text(str(int((self.multiplyer-1)*100))+"%")     

      
        super().handlemessage(msg)
        return None
    def oob_effect(self):
        if self._dead:
            return
        self._dead = True
        if self.multiplyer > 1.25:
            blastType = 'tnt'
            radius = min(self.multiplyer * 5, 20)
        else:
            # penalty for killing people with low multiplyer
            blastType = 'ice'
            radius = 7.5

        Blast(position=self.node.position, blast_radius=radius, blast_type=blastType).autoretain()

# ba_meta export game
class SuperSmashGame(ba.TeamGameActivity[Player, Team]):
    """Game type where last player(s) left alive win."""

    name = 'Super Smash 1.5+'
    description = 'Last remaining alive wins.'
    scoreconfig = ba.ScoreConfig(label='Survived',
                                 scoretype=ba.ScoreType.SECONDS,
                                 none_is_winner=True)
    # Show messages when players die since it's meaningful here.
    announce_player_deaths = True

    @classmethod
    def get_available_settings(
            cls, sessiontype: Type[ba.Session]) -> List[ba.Setting]:
        settings = [
            ba.IntSetting(
                'Lives Per Player',
                default=1,
                min_value=1,
                max_value=10,
                increment=1,
            ),
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
            ba.FloatChoiceSetting(
                'Respawn Times',
                choices=[
                    ('Shorter', 0.25),
                    ('Short', 0.5),
                    ('Normal', 1.0),
                    ('Long', 2.0),
                    ('Longer', 4.0),
                ],
                default=1.0,
            ),
            ba.BoolSetting('Epic Mode', default=False),
        ]
        if issubclass(sessiontype, ba.DualTeamSession):
            settings.append(ba.BoolSetting('Solo Mode', default=False))
            settings.append(
                ba.BoolSetting('Balance Total Lives', default=False))
        return settings

    @classmethod
    def supports_session_type(cls, sessiontype: Type[ba.Session]) -> bool:
        return (issubclass(sessiontype, ba.DualTeamSession)
                or issubclass(sessiontype, ba.FreeForAllSession))

    @classmethod
    def get_supported_maps(cls, sessiontype: Type[ba.Session]) -> List[str]:
        return ba.getmaps('melee')

    def __init__(self, settings: dict):
        super().__init__(settings)
        self._scoreboard = Scoreboard()
        self._start_time: Optional[float] = None
        self._vs_text: Optional[ba.Actor] = None
        self._round_end_timer: Optional[ba.Timer] = None
        self._epic_mode = bool(settings['Epic Mode'])
        self._lives_per_player = int(settings['Lives Per Player'])
        self._time_limit = float(settings['Time Limit'])
        self._balance_total_lives = bool(
            settings.get('Balance Total Lives', False))
        self._solo_mode = bool(settings.get('Solo Mode', False))
        
        # Base class overrides:
        self.slow_motion = self._epic_mode
        self.default_music = (ba.MusicType.EPIC
                              if self._epic_mode else ba.MusicType.SURVIVAL)

    def get_instance_description(self) -> Union[str, Sequence]:
        return 'Last team standing wins.' if isinstance(
            self.session, ba.DualTeamSession) else 'Last one standing wins.'

    def get_instance_description_short(self) -> Union[str, Sequence]:
        return '(Ported by AbhinaYx-ModSquad)' if isinstance(
            self.session, ba.DualTeamSession) else 'last one standing wins'

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

        if self._solo_mode:
            player.team.spawn_order.append(player)
            self._update_solo_mode()
        else:
            # Create our icon and spawn.
            player.icons = [Icon(player, position=(0, 50), scale=0.8)]
            if player.lives > 0:
                self.spawn_player(player)

        # Don't waste time doing this until begin.
        if self.has_begun():
            self._update_icons()

    def on_begin(self) -> None:
        super().on_begin()
        self._pow=None
        self.setup_standard_powerup_drops(enable_tnt=False)
        self._tnt_drop_timer = ba.timer(30, ba.WeakCall(self._dropPowBox), repeat=True)
        self._start_time = ba.time()
        self.setup_standard_time_limit(self._time_limit)
        
        if self._solo_mode:
            self._vs_text = ba.NodeActor(
                ba.newnode('text',
                           attrs={
                               'position': (0, 105),
                               'h_attach': 'center',
                               'h_align': 'center',
                               'maxwidth': 200,
                               'shadow': 0.5,
                               'vr_depth': 390,
                               'scale': 0.6,
                               'v_attach': 'bottom',
                               'color': (0.8, 0.8, 0.3, 1.0),
                               'text': ba.Lstr(resource='vsText')
                           }))

        # If balance-team-lives is on, add lives to the smaller team until
        # total lives match.
        if (isinstance(self.session, ba.DualTeamSession)
                and self._balance_total_lives and self.teams[0].players
                and self.teams[1].players):
            if self._get_total_team_lives(
                    self.teams[0]) < self._get_total_team_lives(self.teams[1]):
                lesser_team = self.teams[0]
                greater_team = self.teams[1]
            else:
                lesser_team = self.teams[1]
                greater_team = self.teams[0]
            add_index = 0
            while (self._get_total_team_lives(lesser_team) <
                   self._get_total_team_lives(greater_team)):
                lesser_team.players[add_index].lives += 1
                add_index = (add_index + 1) % len(lesser_team.players)

        self._update_icons()

        # We could check game-over conditions at explicit trigger points,
        # but lets just do the simple thing and poll it.
        ba.timer(1.0, self._update, repeat=True)

    def _update_solo_mode(self) -> None:
        # For both teams, find the first player on the spawn order list with
        # lives remaining and spawn them if they're not alive.
        for team in self.teams:
            # Prune dead players from the spawn order.
            team.spawn_order = [p for p in team.spawn_order if p]
            for player in team.spawn_order:
                assert isinstance(player, Player)
                if player.lives > 0:
                    if not player.is_alive():
                        self.spawn_player(player)
                    break

    def _update_icons(self) -> None:
        # pylint: disable=too-many-branches

        # In free-for-all mode, everyone is just lined up along the bottom.
        if isinstance(self.session, ba.FreeForAllSession):
            count = len(self.teams)
            x_offs = 85
            xval = x_offs * (count - 1) * -0.5
            for team in self.teams:
                if len(team.players) == 1:
                    player = team.players[0]
                    for icon in player.icons:
                        icon.set_position_and_scale((xval, 30), 0.7)
                        icon.update_for_lives()
                    xval += x_offs

        # In teams mode we split up teams.
        else:
            if self._solo_mode:
                # First off, clear out all icons.
                for player in self.players:
                    player.icons = []

                # Now for each team, cycle through our available players
                # adding icons.
                for team in self.teams:
                    if team.id == 0:
                        xval = -60
                        x_offs = -78
                    else:
                        xval = 60
                        x_offs = 78
                    is_first = True
                    test_lives = 1
                    while True:
                        players_with_lives = [
                            p for p in team.spawn_order
                            if p and p.lives >= test_lives
                        ]
                        if not players_with_lives:
                            break
                        for player in players_with_lives:
                            player.icons.append(
                                Icon(player,
                                     position=(xval, (40 if is_first else 25)),
                                     scale=1.0 if is_first else 0.5,
                                     name_maxwidth=130 if is_first else 75,
                                     name_scale=0.8 if is_first else 1.0,
                                     flatness=0.0 if is_first else 1.0,
                                     shadow=0.5 if is_first else 1.0,
                                     show_death=is_first,
                                     show_lives=False))
                            xval += x_offs * (0.8 if is_first else 0.56)
                            is_first = False
                        test_lives += 1
            # Non-solo mode.
            else:
                for team in self.teams:
                    if team.id == 0:
                        xval = -50
                        x_offs = -85
                    else:
                        xval = 50
                        x_offs = 85
                    for player in team.players:
                        for icon in player.icons:
                            icon.set_position_and_scale((xval, 30), 0.7)
                            icon.update_for_lives()
                        xval += x_offs

    def _get_spawn_point(self, player: Player) -> Optional[ba.Vec3]:
        del player  # Unused.

        # In solo-mode, if there's an existing live player on the map, spawn at
        # whichever spot is farthest from them (keeps the action spread out).
        if self._solo_mode:
            living_player = None
            living_player_pos = None
            for team in self.teams:
                for tplayer in team.players:
                    if tplayer.is_alive():
                        assert tplayer.node
                        ppos = tplayer.node.position
                        living_player = tplayer
                        living_player_pos = ppos
                        break
            if living_player:
                assert living_player_pos is not None
                player_pos = ba.Vec3(living_player_pos)
                points: List[Tuple[float, ba.Vec3]] = []
                for team in self.teams:
                    start_pos = ba.Vec3(self.map.get_start_position(team.id))
                    points.append(
                        ((start_pos - player_pos).length(), start_pos))
                # Hmm.. we need to sorting vectors too?
                points.sort(key=lambda x: x[0])
                return points[-1][1]
        return None
    def spawn_player_spaz(self, player: PlayerType,position: Sequence[float] = (0, 0, 0), angle: float = None) -> MyPlayerSpaz:
        """Create and wire up a ba.PlayerSpaz for the provided ba.Player."""
        # pylint: disable=too-many-locals
        # pylint: disable=cyclic-import

        name = player.getname()
        color = player.color
        highlight = player.highlight

        light_color = _math.normalized_color(color)
        display_color = _ba.safecolor(color, target_intensity=0.75)
        spaz = MyPlayerSpaz(color=color,
                          highlight=highlight,
                          character=player.character,
                          player=player)

        player.actor = spaz
        assert spaz.node
        if position is None:
            # In teams-mode get our team-start-location.
            if isinstance(self.session, DualTeamSession):
                position = (self.map.get_start_position(player.team.id))
            else:
                # Otherwise do free-for-all spawn locations.
                position = self.map.get_ffa_start_position(self.players)
        # If this is co-op and we're on Courtyard or Runaround, add the
        # material that allows us to collide with the player-walls.
        # FIXME: Need to generalize this.
        if isinstance(self.session, CoopSession) and self.map.getname() in [
                'Courtyard', 'Tower D'
        ]:
            mat = self.map.preloaddata['collide_with_wall_material']
            assert isinstance(spaz.node.materials, tuple)
            assert isinstance(spaz.node.roller_materials, tuple)
            spaz.node.materials += (mat, )
            spaz.node.roller_materials += (mat, )

        spaz.node.name = name
        spaz.node.name_color = display_color
        spaz.connect_controls_to_player()
        # Move to the stand position and add a flash of light.
        spaz.handlemessage(
            StandMessage(
                position,
                angle if angle is not None else random.uniform(0, 360)))
        _ba.playsound(self._spawn_sound, 1, position=spaz.node.position)
        light = _ba.newnode('light', attrs={'color': light_color})
        spaz.node.connectattr('position', light, 'position')
        animate(light, 'intensity', {0: 0, 0.25: 1, 0.5: 0})
        _ba.timer(0.5, light.delete)
        return spaz
    def spawn_player(self, player: Player) -> ba.Actor:
        actor = self.spawn_player_spaz(player, self._get_spawn_point(player))
        # If we have any icons, update their state.
        for icon in player.icons:
            icon.handle_player_spawned()
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
        player.icons = []

        # Remove us from spawn-order.
        if self._solo_mode:
            if player in player.team.spawn_order:
                player.team.spawn_order.remove(player)

        # Update icons in a moment since our team will be gone from the
        # list then.
        ba.timer(0, self._update_icons)

    def _get_total_team_lives(self, team: Team) -> int:
        return sum(player.lives for player in team.players)
    def _dropPowBox(self):
        if self._pow is not None and self._pow.exists():
            return
        if len(self.map.tnt_points) == 0:
            return
        pos = random.choice(self.map.tnt_points)
        pos = (pos[0], pos[1] + 1, pos[2])
        self._pow = PowBox(position=pos, velocity=(0, 1, 0))
    def handlemessage(self, msg: Any) -> Any:
        if isinstance(msg, ba.PlayerDiedMessage):

            # Augment standard behavior.
            
            super().handlemessage(msg)
            player: Player = msg.getplayer(Player)
            player.actor.oob_effect()

            player.lives -= 1
            if player.lives < 0:
                ba.print_error(
                    "Got lives < 0 in Elim; this shouldn't happen. solo:" +
                    str(self._solo_mode))
                player.lives = 0

            # If we have any icons, update their state.
            for icon in player.icons:
                icon.handle_player_died()

            # Play big death sound on our last death
            # or for every one in solo mode.
            if self._solo_mode or player.lives == 0:
                ba.playsound(SpazFactory.get().single_player_death_sound)

            # If we hit zero lives, we're dead (and our team might be too).
            if player.lives == 0:
                # If the whole team is now dead, mark their survival time.
                if self._get_total_team_lives(player.team) == 0:
                    assert self._start_time is not None
                    player.team.survival_seconds = int(ba.time() -
                                                       self._start_time)
            else:
                # Otherwise, in regular mode, respawn.
                if not self._solo_mode:
                    self.respawn_player(player)

            # In solo, put ourself at the back of the spawn order.
            if self._solo_mode:
                player.team.spawn_order.remove(player)
                player.team.spawn_order.append(player)

    def _update(self) -> None:
        if self._solo_mode:
            # For both teams, find the first player on the spawn order
            # list with lives remaining and spawn them if they're not alive.
            for team in self.teams:
                # Prune dead players from the spawn order.
                team.spawn_order = [p for p in team.spawn_order if p]
                for player in team.spawn_order:
                    assert isinstance(player, Player)
                    if player.lives > 0:
                        if not player.is_alive():
                            self.spawn_player(player)
                            self._update_icons()
                        break

        # If we're down to 1 or fewer living teams, start a timer to end
        # the game (allows the dust to settle and draws to occur if deaths
        # are close enough).
        if len(self._get_living_teams()) < 2:
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
        results._none_is_winner=True
        self.end(results=results)
