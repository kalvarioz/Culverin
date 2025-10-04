
// ==============================================================================
// RcppGridCascade.cpp
// Rcpp wrapper for high-performance C++ cascade simulation
// ==============================================================================

#include <Rcpp.h>
#include <RcppEigen.h>
#include "grid_cascade.hpp"

// [[Rcpp::depends(RcppEigen)]]
// [[Rcpp::plugins(cpp17)]]
// [[Rcpp::plugins(openmp)]]

using namespace Rcpp;
using namespace grid;

// HELPER FUNCTIONS FOR R <-> C++ CONVERSION
// Convert R data.frame to PowerGridGraph
PowerGridGraph df_to_graph(
    const DataFrame& bus_df,
    const DataFrame& branch_df
) {
  PowerGridGraph graph;
  IntegerVector bus_ids = bus_df["bus_i"];
  NumericVector lons = bus_df["longitude"];
  NumericVector lats = bus_df["latitude"];
  NumericVector loads = bus_df["load_mw"];
  NumericVector gens = bus_df["total_gen"];
  NumericVector voltages = bus_df["vm"];
  for (int i = 0; i < bus_ids.size(); ++i) {
    BusProperties props;
    props.bus_id = bus_ids[i];
    props.longitude = lons[i];
    props.latitude = lats[i];
    props.load_mw = loads[i];
    props.gen_mw = gens[i];
    props.voltage = voltages[i];
    props.is_generator = gens[i] > 0;
    
    graph.add_bus(props);
  }
  IntegerVector from_buses = branch_df["from_bus"];
  IntegerVector to_buses = branch_df["to_bus"];
  NumericVector resistances = branch_df["r"];
  NumericVector reactances = branch_df["x"];
  for (int i = 0; i < from_buses.size(); ++i) {
    BranchProperties props;
    props.resistance = resistances[i];
    props.reactance = reactances[i];
    
    graph.add_branch(from_buses[i], to_buses[i], props);
  }
  
  graph.finalize();
  return graph;
}

// Convert bus locations to C++ map
std::unordered_map<int, Point> df_to_locations(const DataFrame& bus_df) {
  std::unordered_map<int, Point> locations;
  IntegerVector bus_ids = bus_df["bus_i"];
  NumericVector lons = bus_df["longitude"];
  NumericVector lats = bus_df["latitude"];
  
  for (int i = 0; i < bus_ids.size(); ++i) {
    locations[bus_ids[i]] = Point(lons[i], lats[i]);
  }
  
  return locations;
}
// Convert BusSet to R integer vector
IntegerVector busset_to_intvec(const BusSet& buses) {
  IntegerVector result(buses.size());
  int i = 0;
  for (int bus_id : buses) {
    result[i++] = bus_id;
  }
  return result;
}

// EXPORTED R FUNCTIONS

//' Run high-performance cascade simulation
 //' 
 //' @param bus_data data.frame with columns: bus_i, longitude, latitude, load_mw, total_gen, vm
 //' @param branch_data data.frame with columns: from_bus, to_bus, r, x
 //' @param fire_files character vector of fire shapefile paths (one per time step)
 //' @param buffer_km numeric, proximity buffer in kilometers
 //' @param max_steps integer, maximum simulation steps
 //' @param parallel logical, use parallel processing
 //' @return list with simulation results
 //' @export
 // [[Rcpp::export]]
 List run_cpp_cascade(
     DataFrame bus_data,
     DataFrame branch_data,
     CharacterVector fire_files,
     double buffer_km = 5.0,
     int max_steps = 20,
     bool parallel = true,
     bool verbose = true
 ) {
   try {
     Rcout << "Building power grid graph...\n";
     PowerGridGraph initial_graph = df_to_graph(bus_data, branch_data);
     auto bus_locations = df_to_locations(bus_data);
     CascadeSimulator::SimulationConfig config;
     config.buffer_km = buffer_km;
     config.max_steps = max_steps;
     config.parallel = parallel;
     config.verbose = verbose;
     CascadeSimulator simulator(config);
     simulator.set_initial_graph(initial_graph);
     simulator.set_bus_locations(bus_locations);
     std::vector<std::string> fire_paths;
     for (int i = 0; i < fire_files.size(); ++i) {
       fire_paths.push_back(as<std::string>(fire_files[i]));
     }
     simulator.load_fire_sequence(fire_paths);
     Rcout << "Running cascade simulation...\n";
     auto result = simulator.run();
     List step_results;
     for (const auto& step : result.step_results) {
       step_results.push_back(List::create(
           Named("step") = step.step,
           Named("fire_affected") = busset_to_intvec(step.fire_affected),
           Named("cascade_failures") = busset_to_intvec(step.cascade_failures),
           Named("total_lost") = busset_to_intvec(step.total_lost),
           Named("cascade_ratio") = step.cascade_ratio,
           Named("vertices_remaining") = step.metrics.vertices_remaining,
           Named("edges_remaining") = step.metrics.edges_remaining,
           Named("largest_component") = step.metrics.largest_component,
           Named("num_components") = step.metrics.num_components,
           Named("load_served_pct") = step.metrics.load_served_pct,
           Named("gen_served_pct") = step.metrics.gen_served_pct,
           Named("avg_node_strength") = step.metrics.avg_node_strength
       ));
     }
     
     return List::create(
       Named("step_results") = step_results,
       Named("grid_destroyed") = result.grid_destroyed,
       Named("destruction_step") = result.destruction_step,
       Named("num_steps") = result.step_results.size()
     );
     
   } catch (const std::exception& e) {
     stop("C++ cascade simulation failed: " + std::string(e.what()));
   }
 }

//' Detect fire impact on buses
 //' 
 //' @param bus_data data.frame with bus locations
 //' @param fire_file path to fire shapefile
 //' @param buffer_km proximity buffer in km
 //' @return list with affected bus IDs
 //' @export
 // [[Rcpp::export]]
 List detect_fire_impact(
     DataFrame bus_data,
     String fire_file,
     double buffer_km = 5.0
 ) {
   try {
     // Load fire data
     FireImpactDetector detector;
     if (!detector.load_fire_data(as<std::string>(fire_file))) {
       stop("Failed to load fire data");
     }
     auto bus_locations = df_to_locations(bus_data);
     auto impact = detector.detect_impact(bus_locations, buffer_km);
     return List::create(
       Named("direct_contact") = busset_to_intvec(impact.direct_contact),
       Named("proximity_contact") = busset_to_intvec(impact.proximity_contact),
       Named("all_affected") = busset_to_intvec(impact.all_affected),
       Named("total_affected") = impact.all_affected.size()
     );
     
   } catch (const std::exception& e) {
     stop("Fire impact detection failed: " + std::string(e.what()));
   }
 }

//' Generate power difference matrix (for TDA)
 //' 
 //' @param bus_data data.frame with bus power data
 //' @param branch_data data.frame with branch data
 //' @return numeric matrix of pairwise power differences
 //' @export
 // [[Rcpp::export]]
 NumericMatrix generate_power_matrix_cpp(
     DataFrame bus_data,
     DataFrame branch_data
 ) {
   try {
     PowerGridGraph graph = df_to_graph(bus_data, branch_data);
     Eigen::MatrixXd power_diff = graph.get_power_difference_matrix();
     NumericMatrix result(power_diff.rows(), power_diff.cols());
     
     for (int i = 0; i < power_diff.rows(); ++i) {
       for (int j = 0; j < power_diff.cols(); ++j) {
         result(i, j) = power_diff(i, j);
       }
     }
     return result;
     
   } catch (const std::exception& e) {
     stop("Power matrix generation failed: " + std::string(e.what()));
   }
 }

//' Compute grid metrics
 //' 
 //' @param bus_data data.frame with bus data
 //' @param branch_data data.frame with branch data
 //' @return list with grid metrics
 //' @export
 // [[Rcpp::export]]
 List compute_grid_metrics_cpp(
     DataFrame bus_data,
     DataFrame branch_data
 ) {
   try {
     PowerGridGraph graph = df_to_graph(bus_data, branch_data);
     auto metrics = graph.compute_metrics();
     return List::create(
       Named("vertices_remaining") = metrics.vertices_remaining,
       Named("edges_remaining") = metrics.edges_remaining,
       Named("largest_component") = metrics.largest_component,
       Named("num_components") = metrics.num_components,
       Named("load_served_pct") = metrics.load_served_pct,
       Named("gen_served_pct") = metrics.gen_served_pct,
       Named("avg_node_strength") = metrics.avg_node_strength,
       Named("algebraic_connectivity") = metrics.algebraic_connectivity
     );
     
   } catch (const std::exception& e) {
     stop("Metrics computation failed: " + std::string(e.what()));
   }
 }

//' Identify deenergized buses
 //' 
 //' @param bus_data data.frame with bus data
 //' @param branch_data data.frame with branch data
 //' @param removed_buses integer vector of already-removed bus IDs
 //' @return integer vector of deenergized bus IDs
 //' @export
 // [[Rcpp::export]]
 IntegerVector identify_deenergized_cpp(
     DataFrame bus_data,
     DataFrame branch_data,
     IntegerVector removed_buses
 ) {
   try {
     PowerGridGraph graph = df_to_graph(bus_data, branch_data);
     BusSet to_remove;
     for (int i = 0; i < removed_buses.size(); ++i) {
       to_remove.insert(removed_buses[i]);
     }
     graph.remove_buses(to_remove);
     BusSet deenergized = graph.identify_deenergized_buses();
     return busset_to_intvec(deenergized);
   } catch (const std::exception& e) {
     stop("Deenergization detection failed: " + std::string(e.what()));
   }
 }

//' Fast Haversine distance calculation
 //' 
 //' @param lon1 longitude of point 1
 //' @param lat1 latitude of point 1
 //' @param lon2 longitude of point 2
 //' @param lat2 latitude of point 2
 //' @return distance in kilometers
 //' @export
 // [[Rcpp::export]]
 double haversine_distance_cpp(
     double lon1, double lat1,
     double lon2, double lat2
 ) {
   Point p1(lon1, lat1);
   Point p2(lon2, lat2);
   return utils::haversine_distance(p1, p2);
 }

//' Vectorized Haversine distance (from one point to many)
 //' 
 //' @param lon1 scalar longitude
 //' @param lat1 scalar latitude
 //' @param lons vector of longitudes
 //' @param lats vector of latitudes
 //' @return numeric vector of distances in km
 //' @export
 // [[Rcpp::export]]
 NumericVector haversine_distances_vectorized(
     double lon1, double lat1,
     NumericVector lons, NumericVector lats
 ) {
   int n = lons.size();
   NumericVector distances(n);
   Point p1(lon1, lat1);
#pragma omp parallel for
   for (int i = 0; i < n; ++i) {
     Point p2(lons[i], lats[i]);
     distances[i] = utils::haversine_distance(p1, p2);
   }
   
   return distances;
 }

// R PACKAGE INITIALIZATION
//' Initialize GDAL (call once at package load)
 //' @export
 // [[Rcpp::export]]
 void init_gdal() {
   GDALAllRegister();
   Rcout << "GDAL initialized\n";
 }