// ==============================================================================
// grid_cascade.hpp
// High-performance power grid cascade simulation
// Dependencies: Boost Graph Library, Eigen, GDAL/OGR
// ==============================================================================

#ifndef GRID_CASCADE_HPP
#define GRID_CASCADE_HPP

#include <vector>
#include <unordered_map>
#include <unordered_set>
#include <memory>
#include <optional>
#include <string>
#include <algorithm>
#include <execution>
#include <boost/graph/adjacency_list.hpp>
#include <boost/graph/connected_components.hpp>
#include <boost/graph/graph_traits.hpp>
#include <Eigen/Dense>
#include <Eigen/Sparse>
#include <ogr_geometry.h>
#include <ogr_spatialref.h>

// TYPE DEFINITIONS
namespace grid {

// Bus (vertex) properties
struct BusProperties {
  int bus_id;
  double longitude;
  double latitude;
  double load_mw;
  double gen_mw;
  double voltage;
  bool is_generator;
  
  BusProperties() : bus_id(0), longitude(0), latitude(0), 
  load_mw(0), gen_mw(0), voltage(1.0), 
  is_generator(false) {}
};

// Branch (edge) properties
struct BranchProperties {
  double resistance;      // R in p.u.
  double reactance;       // X in p.u.
  double admittance_real; // Real part of Y
  double admittance_imag; // Imaginary part of Y
  double rating;          // MVA rating
  BranchProperties() : resistance(0.01), reactance(0.01), 
  admittance_real(0), admittance_imag(0), 
  rating(100.0) {}
  void compute_admittance() {
    std::complex<double> impedance(resistance, reactance);
    std::complex<double> admittance = 1.0 / impedance;
    admittance_real = admittance.real();
    admittance_imag = admittance.imag();
  }
};

// Graph type definitions
using Graph = boost::adjacency_list<
  boost::vecS,           // Edge container
  boost::vecS,           // Vertex container
  boost::undirectedS,    // Undirected graph
  BusProperties,         // Vertex properties
  BranchProperties       // Edge properties
>;

using Vertex = boost::graph_traits<Graph>::vertex_descriptor;
using Edge = boost::graph_traits<Graph>::edge_descriptor;
using VertexIter = boost::graph_traits<Graph>::vertex_iterator;
using EdgeIter = boost::graph_traits<Graph>::edge_iterator;
using Point = std::pair<double, double>;  // (lon, lat)
using BusSet = std::unordered_set<int>;

// FIRE IMPACT DETECTION
class FireImpactDetector {
private:
  std::vector<OGRPolygon> fire_polygons_;
  std::vector<OGRPoint> fire_centers_;
  OGRSpatialReference spatial_ref_;
  
public:
  FireImpactDetector();
  ~FireImpactDetector();
  bool load_fire_data(const std::string& filepath);
  BusSet find_direct_impact(
      const std::unordered_map<int, Point>& bus_locations
  ) const;
  BusSet find_proximity_impact(
      const std::unordered_map<int, Point>& bus_locations,
      double buffer_km
  ) const;
  struct ImpactResult {
    BusSet direct_contact;
    BusSet proximity_contact;
    BusSet all_affected;
  };
  ImpactResult detect_impact(
      const std::unordered_map<int, Point>& bus_locations,
      double buffer_km = 5.0
  ) const;
};

// GRAPH OPERATIONS
class PowerGridGraph {
private:
  Graph graph_;
  std::unordered_map<int, Vertex> bus_id_to_vertex_;
  std::unordered_map<Vertex, int> vertex_to_bus_id_;
  std::vector<int> generator_buses_;
  
public:
  PowerGridGraph() = default;
  void add_bus(const BusProperties& props);
  void add_branch(int from_bus, int to_bus, const BranchProperties& props);
  void finalize(); // Build index structures
  size_t num_buses() const { return boost::num_vertices(graph_); }
  size_t num_branches() const { return boost::num_edges(graph_); }
  const Graph& get_graph() const { return graph_; }
  Graph& get_graph_mutable() { return graph_; }
  std::optional<Vertex> get_vertex(int bus_id) const;
  std::optional<int> get_bus_id(Vertex v) const;
  BusProperties& get_bus_properties(Vertex v);
  const BusProperties& get_bus_properties(Vertex v) const;
  void remove_buses(const BusSet& buses_to_remove);
  void simplify(); // Remove multi-edges and self-loops
  std::vector<BusSet> get_connected_components() const;
  BusSet identify_deenergized_buses() const;
  Eigen::SparseMatrix<double> get_admittance_matrix() const;
  Eigen::MatrixXd get_power_difference_matrix() const;
  struct GridMetrics {
    size_t vertices_remaining;
    size_t edges_remaining;
    size_t largest_component;
    size_t num_components;
    double load_served_pct;
    double gen_served_pct;
    double avg_node_strength;
    double algebraic_connectivity;
  };
  
  GridMetrics compute_metrics() const;
};
// CASCADE SIMULATION ENGINE

class CascadeSimulator {
public:
  struct SimulationConfig {
    double buffer_km = 5.0;
    size_t max_steps = 20;
    bool parallel = true;
    bool verbose = true;
  };
  struct StepResult {
    size_t step;
    BusSet fire_affected;
    BusSet cascade_failures;
    BusSet total_lost;
    PowerGridGraph::GridMetrics metrics;
    double cascade_ratio;
  };
  struct SimulationResult {
    std::vector<PowerGridGraph> graph_states;
    std::vector<StepResult> step_results;
    std::vector<BusSet> fire_affected_history;
    bool grid_destroyed;
    size_t destruction_step;
  };
  
private:
  SimulationConfig config_;
  PowerGridGraph initial_graph_;
  std::vector<FireImpactDetector> fire_sequence_;
  std::unordered_map<int, Point> bus_locations_;
  StepResult simulate_step(
      PowerGridGraph& current_graph,
      const FireImpactDetector& fire_data,
      size_t step_num
  );
  
public:
  CascadeSimulator(const SimulationConfig& config = SimulationConfig());
  void set_initial_graph(const PowerGridGraph& graph);
  void load_fire_sequence(const std::vector<std::string>& fire_files);
  void set_bus_locations(const std::unordered_map<int, Point>& locations);
  SimulationResult run();
  SimulationResult run_parallel();
};

// UTILITY FUNCTIONS

namespace utils {

inline double deg_to_rad(double deg) {
  return deg * M_PI / 180.0;
}

// Haversine distance between two points (km)
inline double haversine_distance(const Point& p1, const Point& p2) {
  double lat1 = deg_to_rad(p1.second);
  double lon1 = deg_to_rad(p1.first);
  double lat2 = deg_to_rad(p2.second);
  double lon2 = deg_to_rad(p2.first);
  double dlat = lat2 - lat1;
  double dlon = lon2 - lon1;
  double a = std::sin(dlat/2) * std::sin(dlat/2) +
    std::cos(lat1) * std::cos(lat2) *
    std::sin(dlon/2) * std::sin(dlon/2);
  double c = 2 * std::atan2(std::sqrt(a), std::sqrt(1-a));
  return 6371.0 * c;
}

// Create buffer around point (approximate degrees)
inline double km_to_degrees(double km, double latitude) {
  double km_per_degree_lat = 111.0;
  double km_per_degree_lon = 111.0 * std::cos(deg_to_rad(latitude));
  return km / std::max(km_per_degree_lat, km_per_degree_lon);
}
Eigen::VectorXd compute_node_strength(
    const Eigen::SparseMatrix<double>& adjacency
);

double compute_algebraic_connectivity(
    const Eigen::SparseMatrix<double>& laplacian
);

} // namespace utils

} // namespace grid

#endif // GRID_CASCADE_HPP
