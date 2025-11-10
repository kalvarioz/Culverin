use petgraph::{Graph, Undirected};
use nalgebra::DMatrix;
use rayon::prelude::*;
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BusNode {
    pub bus_i: u32,
    pub total_gen: f64,
    pub load_mw: f64,
    pub bus_type: String,
    pub coordinates: (f64, f64),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CascadeStep {
    pub step: u32,
    pub fire_affected: Vec<u32>,
    pub deenergized: Vec<u32>,
    pub vertices_remaining: u32,
    pub edges_remaining: u32,
    pub load_served_pct: f64,
    pub gen_served_pct: f64,
    pub cascade_ratio: f64,
}

#[derive(Debug, Clone)]
pub struct PowerGrid {
    graph: Graph<BusNode, f64, Undirected>,
    bus_lookup: HashMap<u32, petgraph::graph::NodeIndex>,
    generator_buses: HashSet<u32>,
}

impl PowerGrid {
    pub fn new(buses: Vec<BusNode>, edges: Vec<(u32, u32, f64)>) -> Self {
        let mut graph = Graph::new_undirected();
        let mut bus_lookup = HashMap::new();
        let mut generator_buses = HashSet::new();
        
        // Add nodes
        for bus in buses {
            if bus.total_gen > 0.0 {
                generator_buses.insert(bus.bus_i);
            }
            let node_idx = graph.add_node(bus.clone());
            bus_lookup.insert(bus.bus_i, node_idx);
        }
        
        // Add edges
        for (from_bus, to_bus, weight) in edges {
            if let (Some(&from_idx), Some(&to_idx)) = 
                (bus_lookup.get(&from_bus), bus_lookup.get(&to_bus)) {
                graph.add_edge(from_idx, to_idx, weight);
            }
        }
        
        Self { graph, bus_lookup, generator_buses }
    }
    
    pub fn simulate_attack(&mut self, buses_to_remove: &[u32]) -> AttackResult {
        let mut removed_nodes = Vec::new();
        
        // Remove specified buses
        for &bus_id in buses_to_remove {
            if let Some(&node_idx) = self.bus_lookup.get(&bus_id) {
                if self.graph.node_weight(node_idx).is_some() {
                    self.graph.remove_node(node_idx);
                    self.bus_lookup.remove(&bus_id);
                    removed_nodes.push(bus_id);
                }
            }
        }
        
        AttackResult {
            removed_buses: removed_nodes,
            remaining_vertices: self.graph.node_count(),
            remaining_edges: self.graph.edge_count(),
        }
    }
    
    pub fn identify_deenergized_components(&self) -> Vec<u32> {
        use petgraph::algo::connected_components;
        use petgraph::visit::NodeRef;
        
        let components = connected_components(&self.graph);
        let mut deenergized = Vec::new();
        
        // Group nodes by component
        let mut component_nodes: HashMap<usize, Vec<u32>> = HashMap::new();
        for node_idx in self.graph.node_references() {
            let node = node_idx.weight();
            let component_id = components.get(&node_idx.id()).unwrap_or(&0);
            component_nodes.entry(*component_id).or_default().push(node.bus_i);
        }
        
        // Check each component for generators
        for (_, buses_in_component) in component_nodes {
            let has_generator = buses_in_component.iter()
                .any(|bus_id| self.generator_buses.contains(bus_id));
            
            if !has_generator {
                deenergized.extend(buses_in_component);
            }
        }
        
        deenergized
    }
    
    pub fn calculate_power_metrics(&self) -> PowerMetrics {
        let mut total_load = 0.0;
        let mut total_gen = 0.0;
        let mut active_load = 0.0;
        let mut active_gen = 0.0;
        
        for node_ref in self.graph.node_references() {
            let node = node_ref.weight();
            total_load += node.load_mw;
            total_gen += node.total_gen;
            active_load += node.load_mw;
            active_gen += node.total_gen;
        }
        
        PowerMetrics {
            load_served_pct: if total_load > 0.0 { 100.0 * active_load / total_load } else { 0.0 },
            gen_served_pct: if total_gen > 0.0 { 100.0 * active_gen / total_gen } else { 0.0 },
            vertices_remaining: self.graph.node_count(),
            edges_remaining: self.graph.edge_count(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AttackResult {
    pub removed_buses: Vec<u32>,
    pub remaining_vertices: usize,
    pub remaining_edges: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PowerMetrics {
    pub load_served_pct: f64,
    pub gen_served_pct: f64,
    pub vertices_remaining: usize,
    pub edges_remaining: usize,
}

pub struct CascadeEngine {
    initial_grid: PowerGrid,
}

impl CascadeEngine {
    pub fn new(buses: Vec<BusNode>, edges: Vec<(u32, u32, f64)>) -> Self {
        Self {
            initial_grid: PowerGrid::new(buses, edges),
        }
    }
    
    pub async fn run_cascade_simulation(
        &self,
        fire_affected_by_step: Vec<Vec<u32>>,
        max_steps: usize,
    ) -> Vec<CascadeStep> {
        let mut results = Vec::new();
        let mut current_grid = self.initial_grid.clone();
        
        for (step_num, fire_affected) in fire_affected_by_step.into_iter().enumerate() {
            if step_num >= max_steps {
                break;
            }
            
            // Remove fire-affected buses
            let attack_result = current_grid.simulate_attack(&fire_affected);
            
            // Identify cascade failures
            let deenergized = current_grid.identify_deenergized_components();
            
            // Remove deenergized buses
            current_grid.simulate_attack(&deenergized);
            
            // Calculate metrics
            let metrics = current_grid.calculate_power_metrics();
            
            let cascade_ratio = if !fire_affected.is_empty() {
                deenergized.len() as f64 / fire_affected.len() as f64
            } else {
                0.0
            };
            
            results.push(CascadeStep {
                step: step_num as u32 + 1,
                fire_affected: fire_affected.clone(),
                deenergized: deenergized.clone(),
                vertices_remaining: metrics.vertices_remaining as u32,
                edges_remaining: metrics.edges_remaining as u32,
                load_served_pct: metrics.load_served_pct,
                gen_served_pct: metrics.gen_served_pct,
                cascade_ratio,
            });
            
            // Break if grid is completely destroyed
            if current_grid.graph.node_count() == 0 {
                break;
            }
        }
        
        results
    }
}

// Python bindings
use pyo3::prelude::*;

#[pyfunction]
fn create_cascade_engine(
    buses: Vec<(u32, f64, f64, String, f64, f64)>, // bus_i, lon, lat, type, gen, load
    edges: Vec<(u32, u32, f64)>
) -> PyResult<CascadeEngine> {
    let bus_nodes: Vec<BusNode> = buses.into_iter().map(|(bus_i, lon, lat, bus_type, gen, load)| {
        BusNode {
            bus_i,
            total_gen: gen,
            load_mw: load,
            bus_type,
            coordinates: (lon, lat),
        }
    }).collect();
    
    Ok(CascadeEngine::new(bus_nodes, edges))
}

#[pyfunction]
async fn run_cascade_py(
    engine: &CascadeEngine,
    fire_affected_by_step: Vec<Vec<u32>>,
    max_steps: usize,
) -> PyResult<Vec<CascadeStep>> {
    Ok(engine.run_cascade_simulation(fire_affected_by_step, max_steps).await)
}

#[pymodule]
fn cascade_engine(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(create_cascade_engine, m)?)?;
    m.add_function(wrap_pyfunction!(run_cascade_py, m)?)?;
    Ok(())
}