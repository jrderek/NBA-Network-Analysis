import pandas as pd
import numpy as np
import time
import pickle
import argparse

from nba_api.stats.static import teams
from nba_api.stats.static import players

from nba_api.stats.endpoints import playerdashptpass
from nba_api.stats.endpoints import commonallplayers
from nba_api.stats.endpoints import commonplayerinfo


def getPlayersbyTeam(season, team_id):

    allplayers = commonallplayers.CommonAllPlayers(season=season)
    allplayers = allplayers.get_data_frames()[0]
    team_players = allplayers[allplayers['TEAM_ID'] == team_id]
    time.sleep(.600)
    
    return team_players[['TEAM_ID', 'PERSON_ID', 'DISPLAY_LAST_COMMA_FIRST']].values.tolist()

def getBothTeamIDs(team1, team2, season):

    nba_teams = teams.get_teams()
    time.sleep(.600)

    nba_players = players.get_players()
    time.sleep(.600)

    team1_ID = [x['id'] for x in nba_teams if x['nickname'] == team1][0]
    team2_ID = [x['id'] for x in nba_teams if x['nickname'] == team2][0]

    team1_players = getPlayersbyTeam(season, team1_ID)
    team2_players = getPlayersbyTeam(season, team2_ID)
    all_teams = [x['id'] for x in nba_teams]

    return team1_players, team2_players, all_teams

def getAllPlayers(all_teams, season):

    all_players = {}
    for team in all_teams:
        team_players = getPlayersbyTeam(season, team)
        all_players[team] = team_players

    return all_players

def getPassesforPlayers(player_list, season, season_type, all_games=False, n=None):
    
    player_pass_dict = {}
    
    cols_keep = ['PLAYER_ID', 'PLAYER_NAME_LAST_FIRST', 'TEAM_ID', 'PASS_TYPE', 'PASS_TO', 'PASS_TEAMMATE_PLAYER_ID', 'FREQUENCY', 'PASS', 'FGM', 'FGA', 'FG2M', 'FG2A', 'FG3M', 'FG3A']
    
    for x in player_list:
        if all_games:
            passes = playerdashptpass.PlayerDashPtPass(team_id=x[0], player_id=x[1], 
                                                    season=season, season_type_all_star=season_type)
        else:
            passes = playerdashptpass.PlayerDashPtPass(team_id=x[0], player_id=x[1], 
                                                    season=season, season_type_all_star=season_type, last_n_games=n)

        passmade = passes.get_data_frames()[0]
        
        passmade = passmade[cols_keep].rename(columns={'PLAYER_NAME_LAST_FIRST': 'PASS_FROM'})
        
        player_pass_dict[x[1]] = passmade
        time.sleep(.600)
    
    return player_pass_dict

def getShotsforPlayers(passes_dict):
    
    cols_drop = ['PASS_TYPE', 'TEAM_ID', 'PASS_TEAMMATE_PLAYER_ID', 'PASS', 'SHOT_MADE', 'SHOT_MISS', 'TOTAL_SHOTS', 'FGM', 'FGA', 'FG2M', 'FG2A', 'FG3M', 'FG3A']

    allpasses = pd.concat(passes_dict.values(), ignore_index=True)
    allpasses['SHOT_MADE'] = (allpasses['FGM'] + allpasses['FG2M'] + allpasses['FG3M']).astype(int)
    allpasses['SHOT_MISS'] = ((allpasses['FGA'] - allpasses['FGM']) + (allpasses['FG2A'] - allpasses['FG2M']) + (allpasses['FG3A'] - allpasses['FG3M'])).astype(int)
    allpasses['TOTAL_SHOTS'] = (allpasses['SHOT_MADE'] + allpasses['SHOT_MISS']).astype(int)
    allpasses['SHOT_MADE_FREQUENCY'] = round(allpasses['SHOT_MADE']/allpasses['TOTAL_SHOTS'], 3)
    allpasses['SHOT_MADE_FREQUENCY'] = allpasses['SHOT_MADE_FREQUENCY'].fillna(0)
    allpasses['SHOT_MISS_FREQUENCY'] = 1-allpasses['SHOT_MADE_FREQUENCY']

    allpasses = allpasses.drop(columns=cols_drop).rename(columns={'FREQUENCY': 'PASS_FREQUENCY'})
    
    return allpasses

def getPlayerPosition(player_id):
    
    player_info = commonplayerinfo.CommonPlayerInfo(player_id=player_id)
    position = player_info.common_player_info.get_data_frame()['POSITION'][0]
    
    time.sleep(.600)
    return position

def getAllTeamPasses(all_players, season):
    all_team_passes = {}

    cols_drop = ['PASS_TYPE', 'TEAM_ID', 'PASS_TEAMMATE_PLAYER_ID', 'PASS', 'FGM', 'FGA', 'FG2M', 'FG2A', 'FG3M', 'FG3A']

    for key, val in all_players.items():
        team_passes_reg_dict = getPassesforPlayers(val, season, 'Regular Season', all_games=True)
        team_passes_ply_dict = getPassesforPlayers(val, season, 'Playoffs', all_games=True)

        team_passes_reg = pd.concat(team_passes_reg_dict.values(), ignore_index=True)
        team_passes_ply = pd.concat(team_passes_ply_dict.values(), ignore_index=True)

        if team_passes_ply.empty:
            team_passes = team_passes_reg
        else:
            team_passes = team_passes_reg.append(team_passes_ply, ignore_index=True)
        team_passes = team_passes.drop(columns=cols_drop)
        team_passes = team_passes.rename(columns={'PASS_FROM':'FROM', 'PASS_TO':'TO', 'PASS_FREQUENCY':'FREQUENCY'})
        
        all_team_passes[key] = team_passes

    all_nba_passes = pd.concat(all_team_passes.values(), ignore_index=True)

    all_nba_passes['POSITION'] = all_nba_passes['PLAYER_ID'].apply(lambda x : getPlayerPosition(x))
    all_nba_passes_positions = all_nba_passes.groupby(['POSITION']).agg({'FREQUENCY': ['mean', 'std']})
    all_nba_passes_positions.columns = all_nba_passes_positions.columns.droplevel()
    all_nba_passes_positions = all_nba_passes_positions.reset_index()

    return all_nba_passes_positions

def getTeamDicts(team1_players, team2_players, season, season_type):

    team1_dict = {}
    team2_dict = {}
    for i in range(1, 7):
        team1_passes_i = getPassesforPlayers(team1_players, season, season_type, n=i)
        team1_passes_shots_i = getShotsforPlayers(team1_passes_i)
        team1_dict[i] = team1_passes_shots_i

        team2_passes_i = getPassesforPlayers(team2_players, season, season_type, n=i)
        team2_passes_shots_i = getShotsforPlayers(team2_passes_i)
        team2_dict[i] = team2_passes_shots_i

    return team1_dict, team2_dict


if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()

    parser.add_argument('team1', help='The nickname of team 1', type=str)
    parser.add_argument('team2', help='The nickname of team 2', type=str)
    parser.add_argument('season', help='The season of interest', type=str)
    parser.add_argument('season type', help='The season of interest', type=str)
    
    args = vars(parser.parse_args())

    print("Getting players for both teams...")
    team1_players, team2_players, all_teams = getBothTeamIDs(args['team1'], args['team2'], args['season'])
    print("Getting all players for all teams...")
    all_players = getAllPlayers(all_teams, args['season'])
    # print("Getting all passes for all players and positions...")
    # all_nba_passes_positions = getAllTeamPasses(all_players, args['season'])
    print("Getting the two dictionaries for each team...")
    team1_dict, team2_dict = getTeamDicts(team1_players, team2_players, args['season'], args['season type'])
        
    print("Writing team 1 dictionary to file...")
    with open(f"{args['team1']}_dict.pkl","wb") as f:
        pickle.dump(team1_dict, f)

    print("Writing team 2 dictionary to file...")
    with open(f"{args['team2']}_dict.pkl","wb") as f:
        pickle.dump(team2_dict, f)
    # print("Writing all nba passes and positions to file...")
    # all_nba_passes_positions.to_pickle("all_nba_passes.pkl")
