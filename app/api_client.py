import requests
from typing import Optional

# Klient pro komunikaci s REST API backendu
# Zajišťuje autentizaci, správu tokenů a komunikaci se všemi API endpointy
# Obsahuje metody pro správu komponent, montáží, kroků a přihráde k
class ApiClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.token: Optional[str] = None

    # Vrací HTTP hlavičky s autentizačním tokenem pro API požadavky
    # Přidává Authorization header ve formátu "Token <klíč>" pro autentizaci DRF
    # Vrací: slovník s Content-Type a Authorization hlavičkami
    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.token:
            # DRF TokenAuthentication uses "Token <key>"
            headers["Authorization"] = f"Token {self.token}"
        return headers

    # Přihlášení uživatele a získání autentizačního tokenu z backendu
    # Odešle uživatelské jméno a heslo na /api-token-auth/ endpoint
    # Parametry: username (uživatelské jméno), password (heslo)
    # Vrací: True pokud se přihlášení podařilo, False pokud je špatné heslo
    # Vyvolá RuntimeError pokud se vyskytne chyba serveru nebo připojení
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
    
    # Získá seznam všech komponent z API backendu
    # Načte komponenty z endpointu /api/components/
    # Vrací: seznam slovníků obsahujících data komponent (id, name, description, unit, atd.)
    # Vyhledává seznam v odpovědi nebo "results" klíč pro stránkované odpovědi DRF
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

    # Alternativní verze pro získání seznamu komponent s detailnějšími informacemi
    # Používá se pro zobrazení úplného seznamu s id, name, description, unit, component_code a image_path
    # Vrací: seznam slovníků s detailními informacemi o komponentách
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
            if isinstance(data, dict) and "results" in data:  # Stránkovaná odpověď DRF
                return data["results"]
            return []
        else:
            raise RuntimeError(f"Chyba při načítání komponent: {resp.status_code} {resp.text}")

    # Vytvoří novou komponentu v API backendu
    # Odešle POST požadavek na /api/components/ s daty komponenty
    # Parametry: component_code (kód komponenty), name (název), unit (jednotka),
    #            description (popis), image_path (cesta k obrázku)
    # Vrací: slovník s novce vytvořené komponenty včetně ID
    def create_component(self, name: str, unit: str, description: str = "", image_path: str = ""):
        payload = {
            "name": name,
            "unit": unit,
            "description": description,
            "image_path": image_path,
        }
        """
        POST /api/components/

        Tělo požadavku na základě serializeru:
        {
          "name": "...",
          "description": "...",
          "unit": "...",
          "component_code": "...",
          "image_path": "C:/path/to/image.png"
        }
        """
        if not self.token:
            raise RuntimeError("Neautentizován")

        url = f"{self.base_url}/api/components/"
        payload = {
            "name": name,
            "description": description,
            "unit": unit,
            "image_path": image_path,
        }

        resp = requests.post(url, json=payload, headers=self._headers(), timeout=5.0)

        if resp.status_code in (200, 201):
            return resp.json()
        elif resp.status_code == 400:
            raise RuntimeError(f"Chyba ověřování: {resp.text}")
        else:
            raise RuntimeError(f"Chyba při vytváření komponenty: {resp.status_code} {resp.text}")

    def update_component(self, component_id: int, name: str, unit: str, description: str = "", image_path: str = ""):
        payload = {
            "name": name,
            "unit": unit,
            "description": description,
            "image_path": image_path,
        }
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
            "image_path": image_path,
        }

        resp = requests.put(url, json=payload, headers=self._headers(), timeout=5.0)

        if resp.status_code in (200, 202):
            return resp.json()
        elif resp.status_code == 400:
            raise RuntimeError(f"Validation error: {resp.text}")
        else:
            raise RuntimeError(f"Error updating component: {resp.status_code} {resp.text}")
        
    # ===== TYPY MONTÁŽÍ ("Assemblies" v GUI) =====
    # Tento oddíl obsahuje metody pro práci s typy montáží
    # Umožňuje vytváření, čtení a aktualizaci montážních typů

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

    # Vytvoří nový typ montáže v API backendu
    # Odešle POST požadavek na /api/assembly-types/ s parametry montáže
    # Parametry: name (název montáže), description (popis), version (verze, výchozí "1.0"),
    #            is_active (zda je montáž aktivní), image_path (obrázek montáže)
    # Vrací: slovník s novce vytvořeným typem montáže včetně ID
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

    # Aktualizuje existující typ montáže v API backendu
    # Odešle PUT požadavek na /api/assembly-types/<id>/ s novými daty
    # Parametry: assembly_type_id (ID typu k aktualizaci), name, description, version, is_active, image_path
    # Vrací: slovník s aktualizovaným typem montáže
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

    # ===== DETAIL TYPU MONTÁŽE (s kroky atd.) =====
    # Metoda pro získání detailních informací o typu montáže
    # Vrací informace o montáži včetně všech její kroků a objektů

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

    # ===== KROKY MONTÁŽE (AssemblyStep) =====
    # Oddíl obsahuje metody pro správu jednotlivých kroků montáže
    # Kroky jsou součásti typu montáže a definují pořadí a obsah montážního procesu

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

    # Aktualizuje existující krok montáže v API
    # Odešle PUT požadavek na /api/assembly-steps/<id>/ s novými daty
    # Parametry: step_id (ID kroku k aktualizaci), assembly_id, order, title, description
    # Vrací: slovník s aktualizovaným krokem
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

    # Aktualizuje existující krok montáže v API
    # Odešle PUT požadavek na /api/assembly-steps/<id>/ s novými daty
    # Parametry: step_id (ID kroku k aktualizaci), assembly_id, order, title, description
    # Vrací: slovník s aktualizovaným krokem
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


    # ===== PŘIHRÁDK Y (BINS) =====
    # Oddíl pro správu přihráde k (bins) - fyzických míst pro skladování komponent
    # Každá přihrádk a má kód, lokaci a může být přiřazena určité komponentě

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

    # Vytvoří novou přihrádku v API backendu
    # Odešle POST požadavek na /api/bins/ pro vytvoření nového skladovacího místa
    # Parametry: box_code (kód přihrádk y), component_id (ID komponenty v přihrádc e), location (lokace/poloha)
    # Vrací: slovník s novce vytvořenou přihrádkou včetně ID
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

    # Aktualizuje existující přihrádku v API
    # Odešle PUT požadavek na /api/bins/<id>/ s novými daty přihrádk y
    # Parametry: bin_id (ID přihrádk y k aktualizaci), box_code, component_id, location
    # Vrací: slovník s aktualizovanou přihrádkou
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

    # ===== POŽADOVANÉ KOMPONENTY KROKU =====
    # Oddíl pro správu komponent potřebných pro jednotlivé kroky montáže
    # Propojuje konkrétní komponenty a přihrádk y s jednotlivými kroky montáže

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

    # Aktualizuje požadovanou komponentu kroku v API
    # Odešle PUT požadavek na /api/step-required-components/<id>/ s novými daty
    # Parametry: src_id (ID záznamu), step_id (ID kroku), component_id (ID komponenty),
    #            bin_id (ID přihrádk y), quantity (požadované množství)
    # Vrací: slovník s aktualizovaným záznamem
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


    # Smaže požadovanou komponentu kroku z API backendu
    # Odešle DELETE požadavek na /api/step-required-components/<id>/
    # Parametr: src_id (ID záznamu o požadované komponentě)
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

    # ===== OBJEKTY KROKU =====
    # Oddíl pro správu vizuálních objektů v jednotlivých krocích (texty, obrázky)
    # Umožňuje umisťovat a upravovat grafické prvky v UI kroku montáže

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

    # Aktualizuje existující objekt v kroku montáže
    # Odešle PUT požadavek na /api/step-objects/<id>/ s novými pozicemi a daty
    # Parametry: obj_id (ID objektu), step_id, object_type, position_x, position_y,
    #            width, height, z_index, text_content, image_path, font_size
    # Vrací: slovník s aktualizovaným objektem
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

    # Smaže objekt z kroku montáže
    # Odešle DELETE požadavek na /api/step-objects/<id>/
    # Parametr: obj_id (ID objektu k smazání)
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

    # ===== PROVÁDĚNÍ MONTÁŽE / PROVÁDĚNÍ KROKU =====
    # Oddíl pro spouštění a sledování procesu montáže v reálném čase
    # Umožňuje zaznamenávat časy zahájení, dokončení a progress jednotlivých kroků

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

    # Zahájí nové provádění montáže
    # Odešle POST požadavek na /api/assembly-executions/start/ s ID typu montáže
    # Parametr: assembly_type_id (ID typu montáže k provedení)
    # Vrací: slovník s novce vytvořeným provádením včetně ID a času zahájení
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

    # Zahájí provádění konkrétního kroku v rámci probíhající montáže
    # Odešle POST požadavek na /api/assembly-executions/<id>/start_step/
    # Parametry: execution_id (ID provádění montáže), step_id (ID kroku k zahájení)
    # Vrací: slovník s novce vytvořeným provádením kroku včetné ID a času
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

    # Dokonči provádění jednotlivého kroku montáže
    # Odešle POST požadavek na /api/step-executions/<id>/complete/
    # Parametr: step_execution_id (ID provádění kroku k dokončení)
    # Vrací: slovník s aktualizovaným provádením včetně času dokončení
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

def create_run_event(self, payload: dict) -> dict:
    if not self.token:
        raise RuntimeError("Not authenticated")

    url = f"{self.base_url}/api/run-events/"
    try:
        resp = requests.post(url, json=payload, headers=self._headers(), timeout=5.0)
    except requests.RequestException as exc:
        raise RuntimeError(f"Connection error: {exc}") from exc

    if resp.status_code in (200, 201):
        return resp.json()

    raise RuntimeError(f"Error creating run event: {resp.status_code} {resp.text}")