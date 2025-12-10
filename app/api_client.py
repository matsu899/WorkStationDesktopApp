import requests
from typing import Optional


class ApiClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.token: Optional[str] = None

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.token:
            # DRF TokenAuthentication uses "Token <key>"
            headers["Authorization"] = f"Token {self.token}"
        return headers

    def login(self, username: str, password: str) -> bool:
        url = f"{self.base_url}/api-token-auth/"
        payload = {
            "username": username,
            "password": password,
        }

        try:
            resp = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=5.0,
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"Connection error: {exc}") from exc

        if resp.status_code == 200:
            data = resp.json()
            token = data.get("token")
            if not token:
                raise RuntimeError("Login succeeded but no token in response.")
            self.token = token
            return True

        if resp.status_code == 400:
            # wrong username/password
            return False

        raise RuntimeError(f"Server error {resp.status_code}: {resp.text}")
    def get_components(self) -> list[dict]:
        """
        Fetch list of components from API.

        EXPECTED backend endpoint:
          GET /api/components/
        Response: list of objects, e.g.
          [{"id": 1, "code": "C001", "name": "Screw", "description": "M6x20"}, ...]
        """
        if not self.token:
            raise RuntimeError("Not authenticated")

        url = f"{self.base_url}/api/components/"
        resp = requests.get(url, headers=self._headers(), timeout=5.0)

        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                return data
            # in case of paginated DRF: {"results": [...]}
            if isinstance(data, dict) and "results" in data:
                return data["results"]
            return []
        else:
            raise RuntimeError(f"Error loading components: {resp.status_code} {resp.text}")

    def get_components(self) -> list[dict]:
        """
        GET /api/components/

        Expected response: list of objects:
        [
          {
            "id": ...,
            "name": "...",
            "description": "...",
            "unit": "...",
            "component_code": "...",
            "image_path": "..."
          },
          ...
        ]
        """
        if not self.token:
            raise RuntimeError("Not authenticated")

        url = f"{self.base_url}/api/components/"
        resp = requests.get(url, headers=self._headers(), timeout=5.0)

        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "results" in data:  # paginated DRF
                return data["results"]
            return []
        else:
            raise RuntimeError(f"Error loading components: {resp.status_code} {resp.text}")

    def create_component(
        self,
        component_code: str,
        name: str,
        unit: str,
        description: str = "",
        image_path: str = "",
    ) -> dict:
        """
        POST /api/components/

        Body based on your serializer:
        {
          "name": "...",
          "description": "...",
          "unit": "...",
          "component_code": "...",
          "image_path": "C:/path/to/image.png"
        }
        """
        if not self.token:
            raise RuntimeError("Not authenticated")

        url = f"{self.base_url}/api/components/"
        payload = {
            "name": name,
            "description": description,
            "unit": unit,
            "component_code": component_code,
            "image_path": image_path,
        }

        resp = requests.post(url, json=payload, headers=self._headers(), timeout=5.0)

        if resp.status_code in (200, 201):
            return resp.json()
        elif resp.status_code == 400:
            raise RuntimeError(f"Validation error: {resp.text}")
        else:
            raise RuntimeError(f"Error creating component: {resp.status_code} {resp.text}")

    def update_component(
        self,
        component_id: int,
        component_code: str,
        name: str,
        unit: str,
        description: str = "",
        image_path: str = "",
    ) -> dict:
        """
        Update existing component.

        Expected DRF endpoint: PUT /api/components/<id>/
        (ModelViewSet or GenericAPIView with standard router)
        """
        if not self.token:
            raise RuntimeError("Not authenticated")

        url = f"{self.base_url}/api/components/{component_id}/"
        payload = {
            "name": name,
            "description": description,
            "unit": unit,
            "component_code": component_code,
            "image_path": image_path,
        }

        resp = requests.put(url, json=payload, headers=self._headers(), timeout=5.0)

        if resp.status_code in (200, 202):
            return resp.json()
        elif resp.status_code == 400:
            raise RuntimeError(f"Validation error: {resp.text}")
        else:
            raise RuntimeError(f"Error updating component: {resp.status_code} {resp.text}")
        
    # ----- ASSEMBLY TYPES ("Assemblies" in GUI) -----

    def get_assembly_types(self) -> list[dict]:
        """
        GET /api/assembly-types/
        """
        if not self.token:
            raise RuntimeError("Not authenticated")

        url = f"{self.base_url}/api/assembly-types/"
        resp = requests.get(url, headers=self._headers(), timeout=5.0)

        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "results" in data:
                return data["results"]
            return []
        else:
            raise RuntimeError(f"Error loading assemblies: {resp.status_code} {resp.text}")

    def create_assembly_type(
        self,
        name: str,
        description: str = "",
        version: str = "1.0",
        is_active: bool = True,
        image_path: str = "",
    ) -> dict:
        """
        POST /api/assembly-types/
        """
        if not self.token:
            raise RuntimeError("Not authenticated")

        url = f"{self.base_url}/api/assembly-types/"
        payload = {
            "name": name,
            "description": description,
            "version": version,
            "is_active": is_active,
            "image_path": image_path,
        }

        resp = requests.post(url, json=payload, headers=self._headers(), timeout=5.0)

        if resp.status_code in (200, 201):
            return resp.json()
        elif resp.status_code == 400:
            raise RuntimeError(f"Validation error: {resp.text}")
        else:
            raise RuntimeError(f"Error creating assembly type: {resp.status_code} {resp.text}")

    def update_assembly_type(
        self,
        assembly_type_id: int,
        name: str,
        description: str = "",
        version: str = "1.0",
        is_active: bool = True,
        image_path: str = "",
    ) -> dict:
        """
        PUT /api/assembly-types/<id>/
        """
        if not self.token:
            raise RuntimeError("Not authenticated")

        url = f"{self.base_url}/api/assembly-types/{assembly_type_id}/"
        payload = {
            "name": name,
            "description": description,
            "version": version,
            "is_active": is_active,
            "image_path": image_path,
        }

        resp = requests.put(url, json=payload, headers=self._headers(), timeout=5.0)

        if resp.status_code in (200, 202):
            return resp.json()
        elif resp.status_code == 400:
            raise RuntimeError(f"Validation error: {resp.text}")
        else:
            raise RuntimeError(f"Error updating assembly type: {resp.status_code} {resp.text}")

    # ----- ASSEMBLY TYPE DETAIL (with steps etc.) -----

    def get_assembly_type_detail_full(self, assembly_type_id: int) -> dict:
        """
        GET /api/assembly-types/<id>/detail_full/
        Returns AssemblyTypeDetailSerializer:
        {
          "id": ...,
          "name": ...,
          ...
          "steps": [
            {
              "id": ...,
              "assembly": <assembly_id>,
              "order": ...,
              "title": "...",
              "description": "...",
              "required_components": [...],
              "step_objects": [...]
            },
            ...
          ]
        }
        """
        if not self.token:
            raise RuntimeError("Not authenticated")

        url = f"{self.base_url}/api/assembly-types/{assembly_type_id}/detail_full/"
        resp = requests.get(url, headers=self._headers(), timeout=5.0)

        if resp.status_code == 200:
            return resp.json()
        else:
            raise RuntimeError(
                f"Error loading assembly detail: {resp.status_code} {resp.text}"
            )

    # ----- STEPS (AssemblyStep) -----

    def create_step(
        self,
        assembly_id: int,
        order: int,
        title: str,
        description: str = "",
    ) -> dict:
        """
        POST /api/assembly-steps/
        Fields: assembly, order, title, description
        """
        if not self.token:
            raise RuntimeError("Not authenticated")

        url = f"{self.base_url}/api/assembly-steps/"
        payload = {
            "assembly": assembly_id,
            "order": order,
            "title": title,
            "description": description,
        }

        resp = requests.post(url, json=payload, headers=self._headers(), timeout=5.0)

        if resp.status_code in (200, 201):
            return resp.json()
        elif resp.status_code == 400:
            raise RuntimeError(f"Validation error: {resp.text}")
        else:
            raise RuntimeError(f"Error creating step: {resp.status_code} {resp.text}")

    def update_step(
        self,
        step_id: int,
        assembly_id: int,
        order: int,
        title: str,
        description: str = "",
    ) -> dict:
        """
        PUT /api/assembly-steps/<id>/
        """
        if not self.token:
            raise RuntimeError("Not authenticated")

        url = f"{self.base_url}/api/assembly-steps/{step_id}/"
        payload = {
            "assembly": assembly_id,
            "order": order,
            "title": title,
            "description": description,
        }

        resp = requests.put(url, json=payload, headers=self._headers(), timeout=5.0)

        if resp.status_code in (200, 202):
            return resp.json()
        elif resp.status_code == 400:
            raise RuntimeError(f"Validation error: {resp.text}")
        else:
            raise RuntimeError(f"Error updating step: {resp.status_code} {resp.text}")

    def delete_step(self, step_id: int) -> None:
        """
        DELETE /api/assembly-steps/<id>/
        """
        if not self.token:
            raise RuntimeError("Not authenticated")

        url = f"{self.base_url}/api/assembly-steps/{step_id}/"
        resp = requests.delete(url, headers=self._headers(), timeout=5.0)

        if resp.status_code not in (204, 200):
            raise RuntimeError(f"Error deleting step: {resp.status_code} {resp.text}")


    # ----- BINS -----

    def get_bins(self) -> list[dict]:
        """
        GET /api/bins/

        Response example:
        [
          {
            "id": 1,
            "component": {...} or null,
            "box_code": "BIN-01",
            "location": "Shelf A1"
          },
          ...
        ]
        """
        if not self.token:
            raise RuntimeError("Not authenticated")

        url = f"{self.base_url}/api/bins/"
        resp = requests.get(url, headers=self._headers(), timeout=5.0)

        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "results" in data:
                return data["results"]
            return []
        else:
            raise RuntimeError(f"Error loading bins: {resp.status_code} {resp.text}")

    def create_bin(self, box_code: str, component_id: int | None, location: str = "") -> dict:
        """
        POST /api/bins/

        BinSerializer expects:
          component_id (write-only), box_code, location
        """
        if not self.token:
            raise RuntimeError("Not authenticated")

        url = f"{self.base_url}/api/bins/"
        payload = {
            "box_code": box_code,
            "location": location,
            "component_id": component_id,
        }

        resp = requests.post(url, json=payload, headers=self._headers(), timeout=5.0)

        if resp.status_code in (200, 201):
            return resp.json()
        elif resp.status_code == 400:
            raise RuntimeError(f"Validation error: {resp.text}")
        else:
            raise RuntimeError(f"Error creating bin: {resp.status_code} {resp.text}")

    def update_bin(self, bin_id: int, box_code: str, component_id: int | None, location: str = "") -> dict:
        """
        PUT /api/bins/<id>/
        """
        if not self.token:
            raise RuntimeError("Not authenticated")

        url = f"{self.base_url}/api/bins/{bin_id}/"
        payload = {
            "box_code": box_code,
            "location": location,
            "component_id": component_id,
        }

        resp = requests.put(url, json=payload, headers=self._headers(), timeout=5.0)

        if resp.status_code in (200, 202):
            return resp.json()
        elif resp.status_code == 400:
            raise RuntimeError(f"Validation error: {resp.text}")
        else:
            raise RuntimeError(f"Error updating bin: {resp.status_code} {resp.text}")

    # ----- STEP REQUIRED COMPONENTS -----

    def create_step_required_component(
        self,
        step_id: int,
        component_id: int,
        bin_id: int | None,
        quantity: int,
    ) -> dict:
        """
        POST /api/step-required-components/
        If your serializer has `step_id` (write-only) then we must send `step_id`.
        """
        if not self.token:
            raise RuntimeError("Not authenticated")

        url = f"{self.base_url}/api/step-required-components/"
        payload = {
            "step_id": step_id,        
            "component_id": component_id,
            "bin_id": bin_id,
            "quantity": quantity,
        }

        resp = requests.post(url, json=payload, headers=self._headers(), timeout=5.0)
        if resp.status_code in (200, 201):
            return resp.json()
        elif resp.status_code == 400:
            raise RuntimeError(f"Validation error: {resp.text}")
        else:
            raise RuntimeError(
                f"Error creating step required component: {resp.status_code} {resp.text}"
            )

    def update_step_required_component(
        self,
        src_id: int,
        step_id: int,
        component_id: int,
        bin_id: int | None,
        quantity: int,
    ) -> dict:
        """
        PUT /api/step-required-components/<id>/
        """
        if not self.token:
            raise RuntimeError("Not authenticated")

        url = f"{self.base_url}/api/step-required-components/{src_id}/"
        payload = {
            "step_id": step_id,          
            "component_id": component_id,
            "bin_id": bin_id,
            "quantity": quantity,
        }

        resp = requests.put(url, json=payload, headers=self._headers(), timeout=5.0)
        if resp.status_code in (200, 202):
            return resp.json()
        elif resp.status_code == 400:
            raise RuntimeError(f"Validation error: {resp.text}")
        else:
            raise RuntimeError(
                f"Error updating step required component: {resp.status_code} {resp.text}"
            )


    def delete_step_required_component(self, src_id: int) -> None:
        """
        DELETE /api/step-required-components/<id>/
        """
        if not self.token:
            raise RuntimeError("Not authenticated")

        url = f"{self.base_url}/api/step-required-components/{src_id}/"
        resp = requests.delete(url, headers=self._headers(), timeout=5.0)

        if resp.status_code not in (204, 200):
            raise RuntimeError(
                f"Error deleting step required component: {resp.status_code} {resp.text}"
            )

    # ----- STEP OBJECTS -----

    def create_step_object(
        self,
        step_id: int,
        object_type: str,
        position_x: float,
        position_y: float,
        width: float,
        height: float,
        z_index: int,
        text_content: str = "",
        image_path: str = "",
        font_size: int = 40,
    ) -> dict:
        """
        POST /api/step-objects/
        Serializer expects: step_id, object_type, position_x, position_y, width, height, z_index,
                            text_content, image_path
        """
        if not self.token:
            raise RuntimeError("Not authenticated")

        url = f"{self.base_url}/api/step-objects/"
        payload = {
            "step_id": step_id,
            "object_type": object_type,
            "position_x": position_x,
            "position_y": position_y,
            "width": width,
            "height": height,
            "z_index": z_index,
            "text_content": text_content,
            "image_path": image_path,
            "font_size": font_size, 
        }

        resp = requests.post(url, json=payload, headers=self._headers(), timeout=5.0)
        if resp.status_code in (200, 201):
            return resp.json()
        elif resp.status_code == 400:
            raise RuntimeError(f"Validation error: {resp.text}")
        else:
            raise RuntimeError(
                f"Error creating step object: {resp.status_code} {resp.text}"
            )

    def update_step_object(
        self,
        obj_id: int,
        step_id: int,
        object_type: str,
        position_x: float,
        position_y: float,
        width: float,
        height: float,
        z_index: int,
        text_content: str = "",
        image_path: str = "",
        font_size: int = 10,
    ) -> dict:
        """
        PUT /api/step-objects/<id>/
        """
        if not self.token:
            raise RuntimeError("Not authenticated")

        url = f"{self.base_url}/api/step-objects/{obj_id}/"
        payload = {
            "step_id": step_id,
            "object_type": object_type,
            "position_x": position_x,
            "position_y": position_y,
            "width": width,
            "height": height,
            "z_index": z_index,
            "text_content": text_content,
            "image_path": image_path,
            "font_size": font_size,
        }

        resp = requests.put(url, json=payload, headers=self._headers(), timeout=5.0)
        if resp.status_code in (200, 202):
            return resp.json()
        elif resp.status_code == 400:
            raise RuntimeError(f"Validation error: {resp.text}")
        else:
            raise RuntimeError(
                f"Error updating step object: {resp.status_code} {resp.text}"
            )

    def delete_step_object(self, obj_id: int) -> None:
        """
        DELETE /api/step-objects/<id>/
        """
        if not self.token:
            raise RuntimeError("Not authenticated")

        url = f"{self.base_url}/api/step-objects/{obj_id}/"
        resp = requests.delete(url, headers=self._headers(), timeout=5.0)

        if resp.status_code not in (204, 200):
            raise RuntimeError(
                f"Error deleting step object: {resp.status_code} {resp.text}"
            )

    # ===== ASSEMBLY EXECUTION / STEP EXECUTION =====

    def start_assembly_execution(self, assembly_type_id: int) -> dict:
        """
        POST /api/assembly-executions/start/
        Body: {"assembly_type_id": <id>}
        Returns: AssemblyExecution object (id, assembly_type, operator, start_time, ...)
        """
        if not self.token:
            raise RuntimeError("Not authenticated")

        url = f"{self.base_url}/api/assembly-executions/start/"
        payload = {"assembly_type_id": assembly_type_id}

        resp = requests.post(url, json=payload, headers=self._headers(), timeout=5.0)
        if resp.status_code in (200, 201):
            return resp.json()
        elif resp.status_code == 400:
            raise RuntimeError(f"Validation error: {resp.text}")
        else:
            raise RuntimeError(f"Error starting assembly execution: {resp.status_code} {resp.text}")

    def complete_assembly_execution(self, execution_id: int) -> dict:
        """
        POST /api/assembly-executions/<id>/complete/
        Marks assembly execution as completed (end_time + is_completed=True)
        """
        if not self.token:
            raise RuntimeError("Not authenticated")

        url = f"{self.base_url}/api/assembly-executions/{execution_id}/complete/"
        resp = requests.post(url, headers=self._headers(), timeout=5.0)
        if resp.status_code in (200, 201):
            return resp.json()
        elif resp.status_code == 400:
            raise RuntimeError(f"Validation error: {resp.text}")
        else:
            raise RuntimeError(f"Error completing assembly execution: {resp.status_code} {resp.text}")

    def start_step_execution(self, execution_id: int, step_id: int) -> dict:
        """
        POST /api/assembly-executions/<execution_id>/start_step/
        Body: {"step_id": <step_id>}
        Returns: StepExecution object (id, assembly_execution, step, start_time, ...)
        """
        if not self.token:
            raise RuntimeError("Not authenticated")

        url = f"{self.base_url}/api/assembly-executions/{execution_id}/start_step/"
        payload = {"step_id": step_id}

        resp = requests.post(url, json=payload, headers=self._headers(), timeout=5.0)
        if resp.status_code in (200, 201):
            return resp.json()
        elif resp.status_code == 400:
            raise RuntimeError(f"Validation error: {resp.text}")
        else:
            raise RuntimeError(f"Error starting step execution: {resp.status_code} {resp.text}")

    def complete_step_execution(self, step_execution_id: int) -> dict:
        """
        POST /api/step-executions/<id>/complete/
        Marks step execution as completed (end_time + is_completed=True)
        """
        if not self.token:
            raise RuntimeError("Not authenticated")

        url = f"{self.base_url}/api/step-executions/{step_execution_id}/complete/"
        resp = requests.post(url, headers=self._headers(), timeout=5.0)
        if resp.status_code in (200, 201):
            return resp.json()
        elif resp.status_code == 400:
            raise RuntimeError(f"Validation error: {resp.text}")
        else:
            raise RuntimeError(f"Error completing step execution: {resp.status_code} {resp.text}")

