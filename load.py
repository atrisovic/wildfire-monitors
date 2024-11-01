import geopandas as gpd
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import textwrap
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon
from shapely.geometry import Point
import logging
import math
import os

from config import WEATHER_PATH , RURAL_PATH , CTSHAPEFILE_PATH , MONITORS_PATH, STATESHAPEFILE_PATH, TOTALPM25_PATH, SMOKEPM25_PATH

logger = logging.getLogger(name = __name__)

plt.rcParams['font.family'] = 'Times New Roman'

class ExposureDataset:
    def generateExposureDays(self, treshold):
        variable_name = f'{self.exposure}_gt_{treshold}'
        self.df[variable_name] = (self.df[self.exposure]
                                  .apply(lambda s: True if s >= treshold else False)
        )
        return (self.df
                .groupby(['location_label','year'])[variable_name].sum()
                .groupby('location_label').mean()
        ).rename("avg_yrly_"+variable_name)
    
    def getMeanAnnualAverage(self):
        return (self.df
                .groupby(['location_label','year'])[self.exposure].mean()
                .groupby('location_label').mean()
        ).rename(f"avg_yrly_{self.exposure}")
    
    def getAggregateExposure(self, treshold):
        variable_name = f'{self.exposure}_gt_{treshold}'
        return (
            pd.concat([self.generateExposureDays(treshold), 
                       self.getMeanAnnualAverage()], axis=1)
        )


class SmokePMDataset(ExposureDataset):
    def __init__(self, path = None, **kwargs):
        path = path or SMOKEPM25_PATH
        self.exposure = 'smoke_pm'
        logger.info(f"Loading SmokePMDataset from path {path}")
        self.df = pd.read_parquet(path, engine="pyarrow").reset_index()
        self.df = self.df.reset_index()
        self.df = self.df.rename(columns={"date": "time", "FIPS": "location_label", "weighted_pm": self.exposure})

        self.df = self.df[self.getVitalColumns()]
        self.df['year'] = self.df['time'].dt.year
        
        self.treshold = kwargs.get('treshold') or 5

    def getVitalColumns(self):
        return ["time", "location_label", self.exposure]
    

class TotalPM25Dataset(ExposureDataset):
    def __init__(self, path = None, **kwargs):
        path = path or TOTALPM25_PATH
        self.exposure = 'pm25'
        logger.info(f"Loading TotalPM25Dataset from path {path}")
        self.df = pd.read_parquet(path, engine="pyarrow")
        self.df = self.df[self.getVitalColumns()]

        self.df['time'] = pd.to_datetime(self.df['time'])
        self.df = self.df[self.df['time'] >= '2006-01-01']
        self.df = self.df[self.df['time'] <= '2020-12-31']

        self.df['year'] = self.df['time'].dt.year
        
        self.treshold = kwargs.get('treshold') or 5

    def getVitalColumns(self):
        return ["time", "location_label", self.exposure]


class UrbanRuralDataset:
    def __init__(self, path = None, **kwargs):
        path = path or RURAL_PATH
        logger.info(f"Loading UrbanRuralDataset from path {path}")
        self.df = pd.read_csv(path)
        self.df["location_label"] = self.df["GEOID"].str.split("US", expand=True)[1]
        
        self.df['classification'] = self.df.apply(self.classify_urban_rural, axis=1)

    def classify_urban_rural(self, row):
        if row['U7I002'] > row['U7I003']:
            return 'Urban'
        else:
            return 'Rural'

    def getVitalColumns(self):
        return ["location_label", "classification"]

    def getUrbanRuralDataset(self):
        return self.df[self.getVitalColumns()]

class ShapefileDataset:
    def __init__(self, path = None, **kwargs):
        path = path or CTSHAPEFILE_PATH
        logger.info(f"Loading ShapefileDataset from path {path}")
        self.df = gpd.read_file(path)
        self.df["location_label"] = self.df["FIPS"]
        logger.info(f"Shapefile CRS: {self.df.crs}")

        self.df = self.df[self.df['STATE_ABBR']!='TX']
        self.df = self.df[self.getVitalColumns()]

    def getVitalColumns(self):
        return ["location_label", "STATE_ABBR", "POPULATION", "SQMI", "geometry"]

    def getShapefileDataset(self):
        return self.df[self.getVitalColumns()]
    
class MonitorsDataset:
    def __init__(self, path = None, **kwargs):
        path = path or MONITORS_PATH
        logger.info(f"Loading MonitorsDataset from path {path}")
        self.df = pd.read_csv(path)


        df =  self.df.loc[self.df['Parameter Code'] == 88101]
        # EPA PM2.5 standard -- most recent
        df =  df.loc[df['Pollutant Standard'] == 'PM25 Annual 2012']

        gdf_points = gpd.GeoDataFrame(
            df, 
            geometry=[Point(xy) for xy in zip(df["Longitude"], 
                                                df["Latitude"])]
        )
        logger.info(f"Monitors CRS: {gdf_points.Datum.unique()}")

        # Set the CRS for the GeoDataFrame based on the most common projection used with these datums
        gdf_points.crs = 'EPSG:4326'  # EPSG:4326 is a common CRS for both WGS84 and NAD83
        gdf_points = gdf_points.to_crs("ESRI:102003") 
        
        self.shapefile_df = ShapefileDataset().getShapefileDataset()

        self.df = gpd.sjoin(gdf_points, self.shapefile_df, how="inner", predicate="within")
    
    def getMonitorsDataset(self):
        return self.df
    
    def getMonitorsCount(self):
        return self.df.groupby('location_label').size().reset_index(name='monitor_count')
    
    # Python 3 program for the
    # haversine formula
    def haversine(self, lat1, lon1, lat2, lon2):
        # https://www.geeksforgeeks.org/haversine-formula-to-find-distance-between-two-points-on-a-sphere/
        # distance between latitudes
        # and longitudes in KM
        dLat = (lat2 - lat1) * math.pi / 180.0
        dLon = (lon2 - lon1) * math.pi / 180.0
    
        # convert to radians
        lat1 = (lat1) * math.pi / 180.0
        lat2 = (lat2) * math.pi / 180.0
    
        # apply formulae
        a = (pow(math.sin(dLat / 2), 2) +
            pow(math.sin(dLon / 2), 2) *
                math.cos(lat1) * math.cos(lat2));
        rad = 6371
        c = 2 * math.asin(math.sqrt(a))
        return rad * c


    def getClosestMonitor(self):
        self.shapefile_df['center'] = self.shapefile_df['geometry'].centroid
        self.shapefile_df['center'] = self.shapefile_df['center'].to_crs("EPSG:4326")
        
        self.shapefile_df['center'] = self.shapefile_df['center'].apply(lambda coords: Point(coords))

        self.df = self.df.to_crs("EPSG:4326")

        # If the datum is WGS84: Use EPSG:4326.
        # If the datum is NAD83: Use EPSG:4269.

        gdf_points = self.df
        monitors_WGS84 = gdf_points[gdf_points['Datum'] == 'WGS84'].copy()
        monitors_NAD83 = gdf_points[gdf_points['Datum'] == 'NAD83'].copy()
        monitors_NAD83.set_crs("EPSG:4269", inplace=True, allow_override=True)
        monitors_NAD83.to_crs("EPSG:4326", inplace=True)

        gdf = self.shapefile_df
        gdf['distance']=np.inf
        gdf['nearest_monitor'] = None

        monitors_df = pd.concat([monitors_WGS84, monitors_NAD83])
        monitors_df = monitors_df[['Latitude','Longitude']].drop_duplicates().reset_index(names="Site ID")

        logger.info(f"Number of monitors: {monitors_df.shape[0]}")
        logger.info(f"Number of locations: {self.df.shape[0]}")

        for index, row in gdf.iterrows():
            ct_lon, ct_lat = row['center'].x, row['center'].y
            
            min_dist, mon = np.inf, ""
            for _, mon_row in monitors_df.iterrows():
                mon_lon, mon_lat = mon_row['Longitude'], mon_row['Latitude']
                # print(f"CT lat: {ct_lat}, CT lon: {ct_lon}, MON lat: {mon_lat}, MON Lon: {mon_lon}")
                dist = self.haversine(ct_lat, ct_lon, mon_lat, mon_lon)
                if dist < min_dist:
                    min_dist = dist
                    mon = mon_row['Site ID']
                    #print(min_dist)
                    
            gdf.at[index, 'distance'] = min_dist
            gdf.at[index, 'nearest_monitor'] = mon

        #logger.info(f"{gdf['nearest_monitor'].value_counts().head()}")

        return gdf[['location_label', 'nearest_monitor', 'distance']]

    def getMonitors(self):
        ret_df = self.getClosestMonitor().merge(self.getMonitorsCount(), on="location_label", how="left")
        ret_df["monitor_count"] = ret_df["monitor_count"].fillna(0)
        return ret_df

    def plotMonitors(self):
        sdf = gpd.read_file(STATESHAPEFILE_PATH)
        sdf = sdf[sdf['STUSPS'].isin(['AZ', 'CA', 'CO', 'ID', 'MT', 'NV', 'NM', 'OR', 'UT', 'WA','WY'])]
        fig, ax = plt.subplots(1, 1, figsize=(3, 3))

        self.shapefile_df.plot(
            #column=x, 
            ax=ax, 
            color='white',
            edgecolor='lightgrey',
            legend=True, 
            vmax=200,
            linewidth=0.5, 
            #cmap = "viridis_r",
            missing_kwds={"color": "lightgrey"},
            )

        self.df[self.df["State Code"] != 48].plot(ax=ax, color='darkblue', marker='^', markersize=10)
        sdf = sdf.to_crs(self.shapefile_df.crs)
        sdf.boundary.plot(ax=ax, linewidth=0.3, color="grey")
        title_text = "GPS Locations in the Western US"
        wrapped_title = textwrap.fill(title_text, 40)
        ax.set_title(title_text, fontsize=10)
        ax.set_axis_off()

        plt.tight_layout()
        plt.savefig("figures/monitors.png", dpi=300, bbox_inches='tight')

        plt.show()



class MergedExposureDataset:
    def __init__(self, cache_dir='cache', reload=False, **kwargs):
        # Define cache paths
        self.cache_dir = cache_dir
        self.smoke_pm_cache = os.path.join(cache_dir, 'smoke_pm_df.pkl')
        self.total_pm25_cache = os.path.join(cache_dir, 'total_pm25_df.pkl')
        self.urban_rural_cache = os.path.join(cache_dir, 'urban_rural_df.pkl')
        self.shapefile_cache = os.path.join(cache_dir, 'shapefile_df.pkl')
        self.monitors_cache = os.path.join(cache_dir, 'monitors_df.pkl')
        self.merged_cache = os.path.join(cache_dir, 'merged_df.pkl')

        # Create cache directory if it doesn't exist
        os.makedirs(cache_dir, exist_ok=True)

        # Load or generate final merged dataset, considering the reload flag
        self.merged_df = self._load_or_generate(self.merged_cache, self.mergeAll, reload=reload)

    def _load_or_generate(self, cache_path, func, *args, reload=False):
        """Utility function to load a dataframe from cache or generate it."""
        if not reload and os.path.exists(cache_path):
            print(f"Loading cached data from {cache_path}")
            data = pd.read_pickle(cache_path)
            if "geometry" in data.columns:
                data = gpd.GeoDataFrame(data, geometry="geometry", crs="ESRI:102003")

            logger.info("Data loaded from cache.")
            logger.info(f"Data summary: {data.describe()}")
            return data
        else:
            if reload:
                print(f"Reloading data and ignoring cache for {cache_path}.")
            else:
                print(f"Cache not found for {cache_path}. Generating data...")
            
            data = func(*args) if args else func()

            data.to_pickle(cache_path)

            return data
        
    def mergeAll(self):
        # Load or generate each dataset
        self.smoke_pm_df = self._load_or_generate(self.smoke_pm_cache, SmokePMDataset().getAggregateExposure, 5)
        self.total_pm25_df = self._load_or_generate(self.total_pm25_cache, TotalPM25Dataset().getAggregateExposure, 5)
        self.urban_rural_df = self._load_or_generate(self.urban_rural_cache, UrbanRuralDataset().getUrbanRuralDataset)
        self.shapefile_df = self._load_or_generate(self.shapefile_cache, ShapefileDataset().getShapefileDataset)
        self.monitors_df = self._load_or_generate(self.monitors_cache, MonitorsDataset().getMonitors)
                

        self.merged_df = (self.smoke_pm_df
                          .join(self.total_pm25_df, lsuffix='_smoke', rsuffix='_total')
        )
        logger.info(
            f"Number of unique entries after exposure join: {self.merged_df.shape[0]}")
        
        self.merged_df = self.merged_df.join(self.urban_rural_df.set_index('location_label'), on='location_label')
        logger.info(
            f"Number of unique entries after urban/rural join: {self.merged_df.shape[0]}")

        self.merged_df = self.merged_df.join(self.monitors_df.set_index('location_label'), how='left')
        
        logger.info(
            f"Number of locations with monitors: {self.merged_df['monitor_count'].astype(bool).sum(axis=0)}")

        logger.info(
            f"Number of unique entries after monitors join: {self.merged_df.shape[0]}")

        self.merged_df = self.merged_df.join(self.shapefile_df.set_index('location_label'))

        sqmi_to_sqkm = 2.58999
        # Creating a new column 'sqkm' by converting 'sqmi' to square kilometers
        self.merged_df['SQKM'] = self.merged_df['SQMI'] * sqmi_to_sqkm
        self.merged_df["monitors_sqkm"] = self.merged_df["monitor_count"] / self.merged_df["SQKM"] *1000

        self.total_population = self.merged_df["POPULATION"].sum()
        self.merged_df["popw_avg_yrly_smoke_pm"] = self.merged_df["POPULATION"]*5*1000000 / self.total_population

        return self.merged_df


    def getMergedExposure(self):
        return self.merged_df
    
    def getClassifiedStats(self):
        df = self.mergeAll()
        return df.groupby("classification").agg({
            'FIPS':'count',
            'smoke_pm_sum_py': ['sum','mean', 'std', ],  
            'smoke_pm_mean': ['mean', 'std',],
            'pm25_sum_py': ['sum', 'mean', 'std',],
            'pm25_mean': ['mean', 'std',],
            'polluted_over_five_sum_py': ['mean', 'std',],
            'polluted_over_10_sum_py': ['mean', 'std',],
            'polluted_over_35_sum_py': ['mean', 'std',],
            'smoke_pm_gt_5_sum_py': ['mean', 'std', ],  
            'smoke_pm_gt_10_sum_py': ['mean', 'std',],
            'smoke_pm_gt_20_sum_py': ['mean', 'std',],
            'smoke_pm_gt_35_sum_py': ['mean', 'std',],
            'monitor_count': ['count', 'sum'], 
            'monitors_sqkm': ['mean', 'std',],
            'smoke_pm': ['mean', 'std',],
            'pm25': ['mean', 'std',],
        }).round(2).T




