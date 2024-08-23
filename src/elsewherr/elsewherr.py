import requests
import re
import yaml
import sys
from loguru import logger

logger.remove()
logger.add(sys.stdout, level="INFO")
logger.add("debug.log", level="DEBUG")

try:
    logger.debug('Loading Config and setting the list of required Providers')
    config = yaml.safe_load(open("config.yaml"))
except FileNotFoundError:
    logger.error("config.yaml not found")
    sys.exit(1)

requiredProvidersLower = [re.sub('[^A-Za-z0-9]+', '', x).lower() for x in config["requiredProviders"]]
logger.debug(f'requiredProvidersLower: {requiredProvidersLower}')

# Request Headers
radarrHeaders = {'Content-Type': 'application/json', "X-Api-Key":config["radarrApiKey"]}
tmdbHeaders = {'Content-Type': 'application/json'}

# Create all Tags for Providers
logger.debug('Create all Tags for Providers within Radarr')
for requiredProvider in config["requiredProviders"]:
    providerTag = (config["tagPrefix"] + re.sub('[^A-Za-z0-9]+', '', requiredProvider)).lower()
    newTagJson = {
            'label': providerTag,
            'id': 0
        }
    logger.debug(f'newTagJson: {newTagJson}')
    radarrTagsPost = requests.post(config["radarrUrl"]+'/api/v3/tag', json=newTagJson, headers=radarrHeaders)
    logger.debug(f'radarrTagsPost Response: {radarrTagsPost}')

# Get all Tags and create lists of those to remove and add
logger.debug('Get all Tags and create lists of those to remove and add')
radarrTagsGet = requests.get(config["radarrUrl"]+'/api/v3/tag', headers=radarrHeaders)
logger.debug(f'radarrTagsGet Response: {radarrTagsGet}')
existingTags = radarrTagsGet.json()
logger.debug(f'existingTags: {existingTags}')
providerTagsToRemove = []
providerTagsToAdd = []

for existingTag in existingTags:
    if config["tagPrefix"].lower() in existingTag["label"]:
        logger.debug(f'Adding tag [{existingTag}] to the list of tags to be removed')
        providerTagsToRemove.append(existingTag)
    if str(existingTag["label"]).replace(config["tagPrefix"].lower(), '') in requiredProvidersLower:
        logger.debug(f'Adding tag [{existingTag}] to the list of tags to be added')
        providerTagsToAdd.append(existingTag)

# Get all Movies from Radarr
logger.debug('Getting all Movies from Radarr')
radarrResponse = requests.get(config["radarrUrl"]+'/api/v3/movie', headers=radarrHeaders)
logger.debug(f'radarrResponse Response: {radarrResponse}')
movies = radarrResponse.json()
logger.debug(f'Number of Movies: {len(movies)}')

# Work on each movie
logger.debug('Working on all movies in turn')
for movie in movies:
    update = movie
    #time.sleep(1)
    logger.info("-------------------------------------------------------------------------------------------------")
    logger.info("Movie: "+movie["title"])
    logger.info("TMDB ID: "+str(movie["tmdbId"]))
    logger.debug(f'Movie record from Radarr: {movie}')

    logger.debug("Getting the available providers for: "+movie["title"])
    tmdbResponse = requests.get('https://api.themoviedb.org/3/movie/'+str(movie["tmdbId"])+'/watch/providers?api_key='+config["tmdbApiKey"], headers=tmdbHeaders)
    logger.debug(f'tmdbResponse Response: {tmdbResponse}')
    tmdbProviders = tmdbResponse.json()
    logger.debug(f'Total Providers: {len(tmdbProviders["results"])}')

    # Check that flatrate providers exist for the chosen region
    logger.debug("Check that flatrate providers exist for the chosen region")
    try:
        providers = tmdbProviders["results"][config["providerRegion"]]["flatrate"]
        logger.debug(f'Flat Rate Providers: {providers}')
    except KeyError:
        logger.info("No Flatrate Providers")
        continue

    # Remove all provider tags from movie
    logger.debug("Remove all provider tags from movie")
    updateTags = movie.get("tags", [])
    logger.debug(f'updateTags - Start: {updateTags}')
    for providerIdToRemove in (providerIdsToRemove["id"] for providerIdsToRemove in providerTagsToRemove):
        try:
            updateTags.remove(providerIdToRemove)
            logger.debug(f'Removing providerId: {providerIdToRemove}')
        except:
            continue

    # Add all required providers
    logger.debug("Adding all provider tags to movie")
    for provider in providers:
        providerName = provider["provider_name"]
        tagToAdd = (config["tagPrefix"] + re.sub('[^A-Za-z0-9]+', '', providerName)).lower()
        for providerTagToAdd in providerTagsToAdd:
            if tagToAdd in providerTagToAdd["label"]:
                logger.info("Adding tag "+tagToAdd)
                updateTags.append(providerTagToAdd["id"])

    logger.debug(f'updateTags - End: {updateTags}')
    update["tags"] = updateTags
    logger.debug(f'Updated Movie record to send to Radarr: {update}')

    # Update movie in Radarr
    radarrUpdate = requests.put(config["radarrUrl"]+'/api/v3/movie', json=update, headers=radarrHeaders)
    logger.info(radarrUpdate)
