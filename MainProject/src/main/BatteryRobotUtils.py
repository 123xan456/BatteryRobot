import sys
sys.path.append('C:\\Users\\llf1362\\Desktop\\BatteryRobot\\MainProject\\src\\main\\settings')
#add settings folder to path ( otherwise python can't import protocols and settings)

from north import NorthC9
from Locator import *
from PowderShakerUtils import PowderShaker
from powder_protocols import *
import pandas as pd
import time, math

#child of NorthC9 - has all of North's methods plus methods defined in here
class BatteryRobot(NorthC9):
    holding_pipette = False
    holding_vial = False
    cartridge_on_carousel = None
    cartridge_pos= {
        LiOAc: 1    
    }
#     t8 = BatteryRobot('B', network=self.network)

#     def __init__(self):        
#         self.home_robot() #Robot arm homing
#         self.home_carousel() #Robot carousel homing
#         self.home_pump(3)  #Pipette pump homing
#         self.home_pump(0) #Pump system sensing homing
#         self.set_pump_valve(3,0) #Set pump system valve at input position
#         t8 = NorthC9("B", network=c9.network)
#         for temp_channel in range(8):
#             t8.disable_channel(temp_channel) #Clears the temp Sensor

    """
    populate grid of vials with specific powder AND liquid, one vial by one vial
    """
    def dispense_workflow_auto(self, protocol, n_vials = 1, vials_per_col = 4, powder_only = False):
        self.open_clamp()
        self.open_gripper()
        self.zero_scale()
        
        pow_masses = [10,25,50,100,250] #number of elements should equal n_vials/vials_per_col
        liq_volumes = [2, 1, 0.5, 0.25, 0.1, 0.05, 0.025, 0.01] #number of elements should equal n_vials/vials_per_col
        
        data = {
            "Vial_ID": [],
            "time/s":[],
            "PowMass/mg (Intended)":[],
            "PowMass/mg (Real)":[],     
            "LiqVol/ml (Intended)":[],
            "LiqVol/ml (Real)":[]
            }
        
        for dispense_vial_id in range(n_vials):
            data["Vial_ID"].append(dispense_vial_id)
            
            # get vial, place in carousel
            self.get_vial_from_rack(dispense_vial_id, rack_dispense_official)
            self.goto_safe(vial_carousel)
            self.close_clamp()
            self.delay(.7)    
            self.uncap()
            self.holding_vial = False
            self.goto_safe(safe_zone)
            self.open_clamp()
            
            start = time.time()
            
            #dispensing powder 
            col = dispense_vial_id // vials_per_col
            mass = pow_masses[col]
            pow_data = self.dispense_powder_and_scale(protocol, dispense_vial_id, mass)
            
            data["PowMass/mg (Intended)"].append(pow_data["Intended(mg)"])
            data["PowMass/mg (Real)"].append(pow_data["Real(mg)"])
            
            #dispensing liquid
            vol = liq_volumes[col]
            source_vial_id = 0
            
            if dispense_vial_id % 2 == 0:
                source_vial_id = 0 + column * 2
            else:
                source_vial_id = 1 + column * 2
                
            liq_data = self.dispense_liquid_and_scale(dispense_vial_id, source_vial_id, volume)
            data["LiqVol/ml (Intended)"].append(pow_data["Intended(ml)"])
            data["LiqVol/ml (Real)"].append(pow_data["Real(ml)"])
            
            
            t_taken = time.time() - start
            data["time/s"].append(t_taken)
            
            #cap and return to rack
            self.close_clamp()
            self.goto_safe(carousel_cap_approach)
            self.cap()
            self.holding_vial = True
            self.open_clamp()                
            self.goto_safe(rack_dispense_official[dispense_vial_id])
            self.open_gripper()
            self.goto_safe(safe_zone)   
            
        df = pd.DataFrame(data)
        df.to_csv('res/dispense.csv', index=True, mode='w')

    """
    dispense powder into specified vial (dest_id)
    """
    def dispense_powder_and_scale(self, protocol, dest_id, mass, collect_vial = False):
        if collect_vial:
            self.get_vial_from_rack(dest_id, rack_dispense_official)
            self.goto_safe(vial_carousel)
            self.close_clamp()
            self.delay(.7)    
            self.uncap()
            self.holding_vial = False
            self.goto_safe(safe_zone)
            self.open_clamp()
            
        p2 = PowderShaker('C', network = self.network)
        self.check_remove_pipette()
        
        data = {}

        self.move_carousel(68, 77) # carousel moves 68 degrees, 75 mm down
        start = time.time()
        dispensed = p2.cl_pow_dispense(robot = self, mg_target = mass, protocol = protocol)
        p2.set_opening(0)
        t_taken = time.time() - start
        self.delay(1)
        self.move_carousel(0,0)

        data["Vial ID"] = dest_id 
        data["Intended(mg)"] = mass
        data["Real(mg)"] = dispensed
        data["Time Taken(s)"]= t_taken
        return data
    
    """
    Dispense {volume}ml of liquid into vial with id {dest_id} form vial with id {source_id}.
    Destination vials/source vials are from rack_pipette_dispense and rack_pipette_aspirate respectively (see "Locator.py")
    """
    def dispense_liquid_and_scale(self, dest_id, source_id, volume, collect = False):
        pip_id = source_id     
        data = {}
                
        self.check_remove_pipette()

        if collect:
            self.get_vial_from_rack(dest_id, rack_dispense_official)
            self.goto_safe(vial_carousel)
            self.close_clamp()
            self.delay(.7)    
            self.uncap()
            self.holding_vial = False
            self.goto_safe(safe_zone)
            self.open_clamp()
            
        self.get_pipette(pip_id)
        self.open_clamp()
        self.delay(1)
        self.zero_scale()
        
        remaining = volume
        
        for i in range(math.ceil(volume)):
            self.goto_safe(rack_pipette_aspirate[source_id])
            self.aspirate_ml(3, min(remaining,1))
            self.delay(.5)
            self.goto_safe(carousel_dispense)
            self.delay(1)
            self.dispense_ml(3, min(remaining,1))
            self.delay(.5)
            remaining -= 1
            
        self.goto_safe(safe_zone)
        reading = str(self.read_steady_scale())
        self.delay(.5)
        self.remove_pipette()
        self.goto_safe(safe_zone)

        data["Vial ID"] = dest_id 
        data["Intended(ml)"]= volume
        data["Real(ml)"] = reading

        return data
    
    """
    Dispenses powder associated with {protocol} and then dispenses solvent based on desired concentration {conc}
    """
    def make_solution(self, dest_id, source_id, conc, protocol):
        pass
        
                                
    """
    Get vial from {rack_type} at index {vial_id}.
    Examples of {rack_type} are rack_dispense_official and heatplate_official
    Indexing for an n x m rack are as follows:
    
    (n*m)-3 ... 0
    (n*m)-2 ... 1
    (n*m)-1 ... 2
    
    """
    def get_vial_from_rack(self, vial_id, rack_type): #racks/heatplate 
        print(f"getting vial at index {vial_id}")
        self.open_gripper()
        self.goto_safe(rack_type[vial_id])
        self.close_gripper()
        time.sleep(0.5)
        
        #move up to a safe spot where gripper will not collide with anything
        self.move_z(400)
        self.holding_vial = True
        
    """
    If there is a cartridge on carousel (active cartridge), replace with {new}, where {new} is a protocol for a powder
    E.g. get_new_cartridge(LiOAc) replaces the active cartridge (if present) with the LiOAc cartridge
    If {new} is not specified, robot returns active cartridge to holder without replacing it
    Defined protocols can be found in settings/powder_protocols.py
    """
    def get_new_cartridge(self, new=None):
        #ensure carousel is properly aligned for gripper to collect and place cartridge
        self.move_carousel(68,77)
        
        #check if there is an active cartridge 
        if self.cartridge_on_carousel:
            #put active cartridge back to designated holder
            self.goto_safe(active_cartridge)
            self.close_gripper()
            
            if cartridge_pos[active_cartridge] == 1:
                self.goto_safe(powder_1)
            elif cartridge_pos[active_cartridge] == 2:
                self.goto_safe(powder_2)        
            elif cartridge_pos[active_cartridge] == 3:
                self.goto_safe(powder_3)
            elif cartridge_pos[active_cartridge] == 4:
                self.goto_safe(powder_4)
                
            self.open_gripper()
            self.cartridge_on_carousel = None
        
        #if user specifies new, place new cartridge on carousel
        if new:
            if cartridge_pos[new] == 1:
                self.goto_safe(powder_1)
            elif cartridge_pos[new] == 2:
                self.goto_safe(powder_2)        
            elif cartridge_pos[new] == 3:
                self.goto_safe(powder_3)
            elif cartridge_pos[new] == 4:
                self.goto_safe(powder_4)
            self.close_gripper()
            self.goto_safe(active_cartridge)
            self.open_gripper()
            self.cartridge_on_carousel = new
            
         self.goto_safe(safe_zone)
         
    """
    gets new pipette at specified position {pip_index} from pipette rack. Will throw an error if robot is holding a vial.
    Pipette rack is indexed as follows:
      47 ...... 8 5 2
      46 ...... 7 4 1
      45 ...... 6 3 0
    By default, robot takes pipette from index 0 (bottom right corner as shown above)
    """
    def get_pipette(self, pip_index=0):
        # Checks if robot is currently holding a vial, will throw an error if True.
        
        if self.holding_vial:
            raise Exception("Holding vial! Unsafe to perform pipette operations")
        if pip_index > 47:
            raise Exception(f"No pipette at index {pip_index}")
        
        pipette_order = [i for i in range(2, 48, 3)] \
            + [i for i in range(1, 48, 3)] \
            + [i for i in range(0, 48, 3)]
        
        print(f"getting pipette at index {pip_index}")
        self.goto_safe(pipette_grid[pipette_order[pip_index]])
        self.move_z(400) # must lift up before moving to safe spot
        self.move_xyz(100,40,300) # safe spot
        self.holding_pipette = True

    """
    If robot is holding pipette, remove it
    """
    def check_remove_pipette(self):
        if self.holding_pipette:
            print("Rob is holding pipette! Removing pipette...")
            self.remove_pipette()      

    """
    Simple function that removes pipette when robot is holdng it
    """
    def remove_pipette(self):
        self.goto_safe(p_remover_capture_approach)
        self.goto(p_remover_capture)
        self.move_z(400)
        self.holding_pipette = False
    
    

        
        

        

        
        
        
        
