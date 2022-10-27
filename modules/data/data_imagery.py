import xarray
import rioxarray
from modules.data.data_abstract import data_abstract
from owslib.wms import WebMapService
from geopandas import GeoSeries
from shapely.geometry import Polygon
from io import BytesIO


class data_imagery(data_abstract):
    
    # the constructor
    def __init__(self, state, storage_directory = "/pfs/work7/workspace/scratch/tu_zxobe27-ds_project/data/imagery"):
        self.state = state
        self.storage_directory = storage_directory
        
        # prepare stacks
        self.query_bbox = []
        self.out_bbox = []
        self.imgs = []
        self.outnames = []
        
        # provide variables specific to the state
        # - pixel density is the resolution of each pixel in m
        # - import crs is the crs projection used for import
        # - wrs_service is the URL of the service used for download
        match self.state:
            case "brandenburg":
                self.pixel_density = .2
                self.import_crs = 25833
                self.wrs_service = "https://isk.geobasis-bb.de/mapproxy/dop20_2016_2018/service/wms?"
                self.wrs_layer = "dop20_bebb_2016_2018_farbe"
    
    # establishes a connection to the wms service           
    def establish_wms_connection(self):
        self.wms = WebMapService(self.wrs_service, version='1.1.1')
        return([self.wms.identification.title, self.wms.identification.abstract])
    
    # adds a bbox into the query stack
    def add_query_bbox(self, bbox, crs):
        if(crs != self.import_crs):
            self.query_bbox.append(self.project_bounding_box(bbox, crs))
        else:
            self.query_bbox.append(bbox)
    
    # queries all bboxes from the stack    
    def query_wms(self):
        while (len(self.query_bbox) != 0):
            bbox = self.query_bbox.pop()
            # the actual query
            self.imgs.append(self.wms.getmap(
                layers = [self.wrs_layer],
                srs = "EPSG:" + str(self.import_crs),
                bbox = bbox,
                size = self.calculate_image_size(bbox),
                format = "image/jpeg").read())
            # caching the bbox for export
            self.out_bbox.append(bbox)
        
    # exports the downloaded queries to jpg and nc
    def export_downloads(self):
        while (len(self.imgs) != 0):
            jpg = self.imgs.pop()
            bbox = self.out_bbox.pop()
            
            # export as jpg first
            with open(self.storage_directory + "/" + self.state + 
                      "_" + "_".join([str(x) for x in bbox]) + ".jpg", "wb") as file:
                file.write(jpg)
            
            # create xarray  
            tmp_xa = rioxarray.open_rasterio(BytesIO(jpg))
            # set coordinates
            tmp_xa = tmp_xa.assign_coords(x = (tmp_xa.x - .5) * self.pixel_density + bbox[0],
                                          y = (tmp_xa.y - .5) * self.pixel_density + bbox[2])
            # convert type
            tmp_xa = tmp_xa.astype("int")
            # set output crs
            tmp_xa.rio.write_crs(25833, inplace = True)
            tmp_xa.rio.set_spatial_dims(x_dim = "x", y_dim = "y",inplace=True)
            tmp_xa.rio.write_coordinate_system(inplace=True)
            # export
            with open(self.storage_directory + "/" + self.state + 
                      "_" + "_".join([str(x) for x in bbox]) + ".nc", "wb") as file:
                tmp_xa.to_netcdf(file)
 
    # takes a bbox-list of format (xmin, ymin, xmax, ymax) and projects it
    def project_bounding_box(self, bbox, bbox_crs):
        polygon = Polygon([(bbox[0], bbox[1]),
                           (bbox[0], bbox[3]),
                           (bbox[2], bbox[3]),
                           (bbox[2], bbox[1])])
        return(gpd.GeoSeries(polygon).set_crs(crs).to_crs(self.import_crs).bounds)
    
    # calculates the output image size according to the provided density and bbox
    def calculate_image_size(self, bbox):
        return([((bbox[2] - bbox[0]) / self.pixel_density), 
                ((bbox[3] - bbox[1]) / self.pixel_density)])