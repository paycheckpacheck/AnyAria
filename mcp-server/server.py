"""
AnyAria MCP Server

FastAPI server providing MCP endpoints for Claude integration.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging
from pathlib import Path
import sys

# Add AnyAria to path
ANYARIA_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ANYARIA_ROOT / "src"))

from anyaria.core.circuit_generator import CircuitGenerator
from anyaria.core.component_research import ComponentResearcher
from anyaria.simulation.builder import SimulationBuilder

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="AnyAria MCP Server",
    description="AI-powered circuit design server for Claude integration",
    version="0.1.0"
)

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models
class CircuitRequirements(BaseModel):
    """Circuit design requirements"""
    requirements: str
    budget: float = 10.0
    prefer_jlc_stock: bool = True
    ambient_temp: float = 25.0


class ComponentInfo(BaseModel):
    """Component research result"""
    component: str
    analysis: str
    datasheet_url: Optional[str] = None
    equations: List[str] = []
    jlc_part: Optional[str] = None
    price: Optional[float] = None
    in_stock: bool = False


class NetInfo(BaseModel):
    """Net signal information"""
    name: str
    type: str
    min: float
    max: float


class CircuitResponse(BaseModel):
    """Circuit generation response"""
    block_diagram: str
    component_research: List[ComponentInfo]
    simulation_code: str
    nets: List[NetInfo]
    bom: List[Dict[str, Any]]
    total_cost: float
    verification: Dict[str, Any]


# Global instances
generator = CircuitGenerator()
researcher = ComponentResearcher()
sim_builder = SimulationBuilder()


@app.get("/")
async def root():
    """Health check"""
    return {
        "status": "running",
        "service": "AnyAria MCP Server",
        "version": "0.1.0"
    }


@app.post("/generate", response_model=CircuitResponse)
async def generate_circuit(req: CircuitRequirements):
    """
    Generate circuit from requirements

    This is the main endpoint called by the KiCad plugin.
    """
    logger.info(f"Generating circuit: {req.requirements}")

    try:
        # Parse requirements
        parsed = generator.parse_requirements(req.requirements, req.budget)
        logger.info(f"Parsed requirements: {parsed}")

        # Generate block diagram
        blocks = generator.create_block_diagram(parsed)
        logger.info(f"Created {len(blocks)} blocks")

        # Research components (this would fan out to agents in production)
        components = researcher.research_components(
            blocks,
            prefer_jlc=req.prefer_jlc_stock,
            budget=req.budget
        )
        logger.info(f"Researched {len(components)} components")

        # Generate circuit with circuit-synth
        circuit = generator.build_circuit(blocks, components)
        logger.info(f"Built circuit with {len(circuit.components)} components")

        # Generate simulation code
        sim_code = sim_builder.generate_simulation(circuit, blocks)
        logger.info("Generated simulation code")

        # Extract net information
        nets = [
            NetInfo(
                name=net.name,
                type=net.type,
                min=net.voltage_min,
                max=net.voltage_max
            )
            for net in circuit.nets
        ]

        # Calculate BOM
        bom = [
            {
                "ref": c.reference,
                "value": c.value,
                "footprint": c.footprint,
                "price": c.price,
                "jlc_part": c.jlc_part
            }
            for c in circuit.components
        ]
        total_cost = sum(c.price for c in circuit.components if c.price)

        # Verification
        verification = generator.verify_design(
            circuit,
            parsed,
            ambient_temp=req.ambient_temp
        )

        return CircuitResponse(
            block_diagram=generator.format_block_diagram(blocks),
            component_research=[
                ComponentInfo(
                    component=c.description,
                    analysis=c.analysis,
                    datasheet_url=c.datasheet_url,
                    equations=c.equations,
                    jlc_part=c.jlc_part,
                    price=c.price,
                    in_stock=c.in_stock
                )
                for c in components
            ],
            simulation_code=sim_code,
            nets=nets,
            bom=bom,
            total_cost=total_cost,
            verification=verification
        )

    except Exception as e:
        logger.error(f"Circuit generation failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/simulate")
async def run_simulation(code: str, inputs: Dict[str, Any]):
    """
    Run Python simulation code

    Execute simulation and return results.
    """
    try:
        result = sim_builder.execute_simulation(code, inputs)
        return {"success": True, "result": result}
    except Exception as e:
        logger.error(f"Simulation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/jlc/search")
async def search_jlc(query: str, category: Optional[str] = None):
    """
    Search JLC PCB component database

    Query JLC PCB for components matching search terms.
    """
    try:
        results = researcher.search_jlc_pcb(query, category)
        return {"results": results}
    except Exception as e:
        logger.error(f"JLC search failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
