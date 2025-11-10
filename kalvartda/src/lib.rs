use nalgebra::DMatrix;
use ndarray::Array2;
use rayon::prelude::*;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BusData {
    pub bus_i: u32,
    pub longitude: f64,
    pub latitude: f64,
    pub total_gen: f64,
    pub load_mw: f64,
    pub vm: f64,
    pub base_kv: f64,
    pub bus_type: String,
    pub zone: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CascadeConfig {
    pub fire_impact_buffer_km: f64,
    pub simulation_steps: u32,
    pub analysis_radius_km: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PersistenceFeature {
    pub dimension: u8,
    pub birth: f64,
    pub death: f64,
    pub persistence: f64,
}

pub struct TDAEngine {
    buses: Vec<BusData>,
    power_matrix: Option<DMatrix<f64>>,
    config: CascadeConfig,
}

impl TDAEngine {
    pub fn new(buses: Vec<BusData>, config: CascadeConfig) -> Self {
        Self {
            buses,
            power_matrix: None,
            config,
        }
    }

    // High-performance matrix generation
    pub fn generate_power_matrix(&mut self) -> anyhow::Result<()> {
        let n = self.buses.len();
        let mut matrix = DMatrix::zeros(n, n);
        
        // Parallel matrix computation
        matrix.par_iter_mut().enumerate().for_each(|(idx, element)| {
            let (i, j) = (idx / n, idx % n);
            if i != j {
                *element = self.compute_power_distance(i, j);
            }
        });
        
        self.power_matrix = Some(matrix);
        Ok(())
    }

    fn compute_power_distance(&self, i: usize, j: usize) -> f64 {
        let bus_i = &self.buses[i];
        let bus_j = &self.buses[j];
        
        // Multi-factor distance calculation
        let power_diff = (bus_i.total_gen - bus_i.load_mw) - (bus_j.total_gen - bus_j.load_mw);
        let voltage_diff = bus_i.vm - bus_j.vm;
        let spatial_dist = ((bus_i.longitude - bus_j.longitude).powi(2) + 
                           (bus_i.latitude - bus_j.latitude).powi(2)).sqrt();
        
        // Weighted combination
        (power_diff.abs() * 0.4 + voltage_diff.abs() * 0.3 + spatial_dist * 0.3).abs()
    }

    // Perseus interface
    pub fn run_perseus_analysis(&self, output_dir: &str) -> anyhow::Result<Vec<PersistenceFeature>> {
        let matrix = self.power_matrix.as_ref()
            .ok_or_else(|| anyhow::anyhow!("Power matrix not generated"))?;
        
        // Write Perseus input
        self.write_perseus_file(matrix, output_dir)?;
        
        // Execute Perseus
        let output = std::process::Command::new("Perseus/perseusWin.exe")
            .args(&["distmat", &format!("{}/M.txt", output_dir), &format!("{}/Moutput", output_dir)])
            .output()?;
        
        if !output.status.success() {
            return Err(anyhow::anyhow!("Perseus execution failed"));
        }
        
        // Parse results
        self.parse_perseus_output(output_dir)
    }

    fn write_perseus_file(&self, matrix: &DMatrix<f64>, output_dir: &str) -> anyhow::Result<()> {
        use std::fs;
        use std::io::Write;
        
        fs::create_dir_all(output_dir)?;
        
        let mut file = fs::File::create(format!("{}/M.txt", output_dir))?;
        
        // Perseus format
        writeln!(file, "{}", matrix.nrows())?;
        writeln!(file, "0 0.05 10 3")?; // g s N C parameters
        
        for element in matrix.iter() {
            write!(file, "{} ", if *element == 0.0 { 999.0 } else { *element })?;
        }
        
        Ok(())
    }

    fn parse_perseus_output(&self, output_dir: &str) -> anyhow::Result<Vec<PersistenceFeature>> {
        use std::fs;
        
        let mut features = Vec::new();
        
        // Parse dimension 0 and 1 files
        for dim in 0..=1 {
            let file_path = format!("{}/Moutput_{}.txt", output_dir, dim);
            if let Ok(content) = fs::read_to_string(&file_path) {
                for line in content.lines() {
                    let parts: Vec<&str> = line.split_whitespace().collect();
                    if parts.len() >= 2 {
                        let birth: f64 = parts[0].parse()?;
                        let mut death: f64 = parts[1].parse().unwrap_or(11.0);
                        
                        if death == -1.0 {
                            death = 11.0;
                        }
                        
                        // Normalize
                        let birth_norm = birth / 11.0;
                        let death_norm = death / 11.0;
                        
                        features.push(PersistenceFeature {
                            dimension: dim as u8,
                            birth: birth_norm,
                            death: death_norm,
                            persistence: death_norm - birth_norm,
                        });
                    }
                }
            }
        }
        
        Ok(features)
    }

    // Wasserstein distance calculation
    pub fn compute_wasserstein_distance(
        &self, 
        features1: &[PersistenceFeature], 
        features2: &[PersistenceFeature]
    ) -> f64 {
        // Simplified Wasserstein distance
        let total_pers1: f64 = features1.iter().map(|f| f.persistence).sum();
        let total_pers2: f64 = features2.iter().map(|f| f.persistence).sum();
        
        (total_pers1 - total_pers2).abs() + 
        (features1.len() as f64 - features2.len() as f64).abs() * 0.1
    }
}

// Python bindings
use pyo3::prelude::*;

#[pyfunction]
fn create_engine(buses: Vec<(u32, f64, f64, f64, f64, f64, f64, String, u32)>, config: (f64, u32, f64)) -> PyResult<TDAEngine> {
    let bus_data: Vec<BusData> = buses.into_iter().map(|(bus_i, lon, lat, gen, load, vm, kv, bus_type, zone)| {
        BusData {
            bus_i, longitude: lon, latitude: lat, total_gen: gen, 
            load_mw: load, vm, base_kv: kv, bus_type, zone
        }
    }).collect();
    
    let cascade_config = CascadeConfig {
        fire_impact_buffer_km: config.0,
        simulation_steps: config.1,
        analysis_radius_km: config.2,
    };
    
    Ok(TDAEngine::new(bus_data, cascade_config))
}

#[pymodule]
fn tda_engine(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(create_engine, m)?)?;
    Ok(())
}