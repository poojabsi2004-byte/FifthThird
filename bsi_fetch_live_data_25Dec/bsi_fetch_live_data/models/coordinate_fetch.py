from odoo import models, api
import xmlrpc.client
import logging
import re
from datetime import datetime
import psycopg2
from odoo import models, fields, api
import requests
_logger = logging.getLogger(__name__)

class GeoLocationSync(models.Model):
    _name = 'geo.location.sync'
    _description = 'Sync Geo Location from Odoo 15'

    # cordinate location start

    def normalize_state_name(self, name):
        if not name:
            return ''
        return re.sub(r'\s*\(.*\)$', '', name).strip()

    @api.model
    def sync_attendance_data(self):
        url = 'https://jbmenterprisellc.com'
        db = 'Subway_with_5_stores'
        username = 'admin'
        password = 'Bot#753'

        try:
            common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
            uid = common.authenticate(db, username, password, {})
            if not uid:
                _logger.error("❌ Authentication failed to Odoo 15 (xmlrpc).")
                return
            models_15 = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')
        except Exception as e:
            _logger.exception("Failed to connect to remote Odoo 15: %s", e)
            return

        try:
            remote_ids = models_15.execute_kw(
                db, uid, password,
                'hr.attendance', 'search',
                [[]]
            )
        except Exception as e:
            _logger.exception("Error searching remote hr.attendance: %s", e)
            return

        if not remote_ids:
            _logger.info("No hr.attendance records found on Odoo 15.")
            return

        fields_to_read = ['employee_id', 'store_id', 'check_in', 'check_out', 'checkout_store_id', 'worked_hours']
        try:
            remote_attendances = models_15.execute_kw(
                db, uid, password,
                'hr.attendance', 'read',
                [remote_ids],
                {'fields': fields_to_read}
            )
        except Exception as e:
            _logger.exception("Error reading remote hr.attendance records: %s", e)
            return

        created, updated = 0, 0

        for rec in remote_attendances:
            emp_15 = rec.get('employee_id')
            if emp_15:
                emp_name = emp_15[1] if isinstance(emp_15, (list, tuple)) and len(emp_15) > 1 else str(emp_15)
            else:
                emp_name = "Unknown Employee"

            employee = self.env['hr.employee'].search([('name', '=', emp_name)], limit=1)
            if not employee:
                employee = self.env['hr.employee'].create({'name': emp_name})
                _logger.info("Created employee '%s' in V18 (id=%s)", emp_name, employee.id)

            employee_18_id = employee.id

            def _map_store_field(remote_store_field):
                if not remote_store_field:
                    return False
                store_name = remote_store_field[1] if isinstance(remote_store_field, (list, tuple)) and len(remote_store_field) > 1 else str(remote_store_field)
                store = self.env['store.store'].search([('name', '=', store_name)], limit=1)
                if not store:
                    store = self.env['store.store'].create({'name': store_name})
                    _logger.info("Created store '%s' in V18 (id=%s)", store_name, store.id)
                return store.id

            store_id_18 = _map_store_field(rec.get('store_id'))
            checkout_store_id_18 = _map_store_field(rec.get('checkout_store_id'))

            check_in_raw, check_out_raw = rec.get('check_in'), rec.get('check_out')
            try:
                check_in_dt = fields.Datetime.to_datetime(check_in_raw) if check_in_raw else False
            except Exception:
                check_in_dt = check_in_raw

            try:
                check_out_dt = fields.Datetime.to_datetime(check_out_raw) if check_out_raw else False
            except Exception:
                check_out_dt = check_out_raw

            attendance_vals = {
                'employee_id': employee_18_id,
                'store_id': store_id_18 or False,
                'check_in': check_in_dt or False,
                'check_out': check_out_dt or False,
                'checkout_store_id': checkout_store_id_18 or False,
                'worked_hours': rec.get('worked_hours') or 0.0,
            }

            domain = [('employee_id', '=', employee_18_id)]
            if check_in_dt:
                domain.append(('check_in', '=', check_in_dt))
            elif check_out_dt:
                domain.append(('check_out', '=', check_out_dt))

            existing = self.env['hr.attendance'].search(domain, limit=1)
            if existing:
                try:
                    existing.write({k: v for k, v in attendance_vals.items() if v not in (False, None, '')})
                    updated += 1
                except Exception as e:
                    _logger.exception("Failed to update attendance id %s: %s", existing.id, e)
            else:
                try:
                    self.env['hr.attendance'].create(attendance_vals)
                    created += 1
                except Exception as e:
                    _logger.exception("Failed to create attendance for employee %s (remote id %s): %s", employee_18_id, rec.get('id'), e)

        _logger.info("✅ Attendance sync completed. Created: %s, Updated: %s", created, updated)
        return {
            'created': created,
            'updated': updated,
        }

    @api.model
    def sync_geo_location_data(self):
        url = 'https://jbmenterprisellc.com'
        db = 'Subway_with_5_stores'
        username = 'admin'
        password = 'Bot#753'

        common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
        uid = common.authenticate(db, username, password, {})
        if not uid:
            _logger.error("❌ Authentication failed to Odoo 15")
            return

        models_15 = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')

        geo_location_ids = models_15.execute_kw(
            db, uid, password,
            'emp.geo_location', 'search',
            [[]]
        )

        if not geo_location_ids:
            _logger.info("No geo_location records found in Odoo 15.")
            return

        geo_locations = models_15.execute_kw(
            db, uid, password,
            'emp.geo_location', 'read',
            [geo_location_ids],
            {
                'fields': [
                    'name', 'store_id', 'area_ids',
                    'street', 'street2', 'city', 'state_id', 'zip', 'country_id'
                ]
            }
        )

        for geo in geo_locations:
            store_18_id = False
            store_id_15 = geo.get('store_id')
            if store_id_15:
                store_name = store_id_15[1]
                store = self.env['store.store'].search([('name', '=', store_name)], limit=1)
                if not store:
                    store = self.env['store.store'].create({'name': store_name})
                store_18_id = store.id

            country_18_id = False
            country_id_15 = geo.get('country_id')
            if country_id_15:
                country_name = country_id_15[1]
                country = self.env['res.country'].search([('name', 'ilike', country_name)], limit=1)
                if country:
                    country_18_id = country.id
                else:
                    _logger.warning(f"Country '{country_name}' not found.")

            state_18_id = False
            state_id_15 = geo.get('state_id')
            if state_id_15:
                state_id_15_id = state_id_15[0]
                state_id_15_name = state_id_15[1]
                print(f"Odoo 15 state_id.id: {state_id_15_id}, state_id.name: {state_id_15_name}")

                normalized_state_name = self.normalize_state_name(state_id_15_name)
                _logger.info(f"Trying to sync normalized state name: '{normalized_state_name}'")

                domain = [('name', '=', normalized_state_name)]
                if country_18_id:
                    domain.append(('country_id', '=', country_18_id))

                state = self.env['res.country.state'].search(domain, limit=1)
                if state:
                    state_18_id = state.id
                    _logger.info(f"Found state in Odoo 18: {state.name} (ID: {state.id})")
                else:
                    _logger.warning(f"State '{normalized_state_name}' not found in res.country.state with country ID {country_18_id}")
            else:
                _logger.info("No state_id provided in source record.")

            geo_loc = self.env['emp.geo_location'].create({
                'name': geo.get('name'),
                'store_id': store_18_id,
                'street': geo.get('street') or '',
                'street2': geo.get('street2') or '',
                'city': geo.get('city') or '',
                'zip': geo.get('zip') or '',
                'state_id': state_18_id,
                'country_id': country_18_id,
            })

            area_ids_15 = geo.get('area_ids', [])
            if not area_ids_15:
                continue

            areas_15 = models_15.execute_kw(
                db, uid, password,
                'geo_location.area', 'read',
                [area_ids_15],
                {'fields': ['name', 'coordinate_ids']}
            )

            for area in areas_15:
                coord_ids_15 = area.get('coordinate_ids', [])
                coords_15 = []
                if coord_ids_15:
                    coords_15 = models_15.execute_kw(
                        db, uid, password,
                        'area.coordinate', 'read',
                        [coord_ids_15],
                        {'fields': ['x', 'y']}
                    )

                coord_18_ids = []
                for coord in coords_15:
                    x = coord.get('x')
                    y = coord.get('y')
                    coord_obj = self.env['area.coordinate'].search([
                        ('x', '=', x), ('y', '=', y)
                    ], limit=1)
                    if not coord_obj:
                        coord_obj = self.env['area.coordinate'].create({'x': x, 'y': y})
                    coord_18_ids.append(coord_obj.id)

                self.env['geo_location.area'].create({
                    'name': area.get('name'),
                    'coordinate_ids': [(6, 0, coord_18_ids)],
                    'empgeo_id': geo_loc.id,
                })

        _logger.info("✅ Geo location sync completed successfully.")
    # cordinate location end

    # @api.model
    # def sync_geo_location_data_remaining(self):
    #     # --- configuration for remote Odoo 15 ---
    #     url = 'http://192.168.29.162:8069/'
    #     db = 'Subway_DATA'
    #     username = 'admin'
    #     password = 'Bot#753'

    #     # List of specific IDs to transfer from Odoo 15
    #     remote_ids = [446,447,448,449,450,451,452,453,454]

    #     # try:
    #     #     common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
    #     #     uid = common.authenticate(db, username, password, {})
    #     #     if not uid:
    #     #         return
    #     # except Exception as e:
    #     #     _logger.exception("❌ Failed to authenticate to remote Odoo: %s", e)
    #     #     return


    #     url = "http://192.168.29.162:8069"
    #     db = "Subway_DATA"
    #     username = "admin"
    #     password = "Bot#753"
    #     common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    #     uid = common.authenticate(db, username, password, {})
    #     print(uid)
    #     _logger.error("\n\nUSERRRRRRRRRR", uid)
    #     _logger.info("\n\nUSERRRRRRRRRR", uid)

    #     models_15 = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')

    #     # get the remote records by explicit ids
    #     try:
    #         geo_location_ids = models_15.execute_kw(
    #             db, uid, password,
    #             'emp.geo_location', 'search',
    #             [[('id', 'in', remote_ids)]]
    #         )
    #     except Exception as e:
    #         _logger.exception("❌ Remote search for emp.geo_location failed: %s", e)
    #         return

    #     if not geo_location_ids:
    #         _logger.info("No specified geo_location records found in Odoo 15 for ids: %s", remote_ids)
    #         return

    #     try:
    #         geo_locations = models_15.execute_kw(
    #             db, uid, password,
    #             'emp.geo_location', 'read',
    #             [geo_location_ids],
    #             {
    #                 'fields': [
    #                     'id', 'name', 'store_id', 'area_ids',
    #                     'street', 'street2', 'city', 'state_id', 'zip', 'country_id'
    #                 ]
    #             }
    #         )
    #     except Exception as e:
    #         _logger.exception("❌ Remote read for emp.geo_location failed: %s", e)
    #         return

    #     for geo in geo_locations:
    #         try:
    #             remote_id = geo.get('id')
    #             store_18_id = False
    #             store_id_15 = geo.get('store_id')
    #             if store_id_15:
    #                 store_name = store_id_15[1]
    #                 store = self.env['store.store'].search([('name', '=', store_name)], limit=1)
    #                 if not store:
    #                     store = self.env['store.store'].create({'name': store_name})
    #                 store_18_id = store.id

    #             country_18_id = False
    #             country_id_15 = geo.get('country_id')
    #             if country_id_15:
    #                 country_name = country_id_15[1]
    #                 country = self.env['res.country'].search([('name', 'ilike', country_name)], limit=1)
    #                 if country:
    #                     country_18_id = country.id
    #                 else:
    #                     _logger.warning("Country '%s' not found in v18; leaving country_id empty for remote id %s", country_name, remote_id)

    #             state_18_id = False
    #             state_id_15 = geo.get('state_id')
    #             if state_id_15:
    #                 state_id_15_name = state_id_15[1]
    #                 _logger.info("Trying to sync normalized state name: '%s' for remote id %s", state_id_15_name, remote_id)

    #                 # normalize if you have function; using your normalize_state_name() call if present
    #                 try:
    #                     normalized_state_name = self.normalize_state_name(state_id_15_name)
    #                 except Exception:
    #                     normalized_state_name = state_id_15_name

    #                 domain = [('name', '=', normalized_state_name)]
    #                 if country_18_id:
    #                     domain.append(('country_id', '=', country_18_id))

    #                 state = self.env['res.country.state'].search(domain, limit=1)
    #                 if state:
    #                     state_18_id = state.id
    #                     _logger.info("Found state in Odoo 18: %s (ID: %s) for remote id %s", state.name, state.id, remote_id)
    #                 else:
    #                     _logger.warning("State '%s' not found in res.country.state with country ID %s for remote id %s", normalized_state_name, country_18_id, remote_id)
    #             else:
    #                 _logger.info("No state_id provided in remote record (id %s).", remote_id)

    #             # --- Avoid duplicates: try to find existing by name + store (customize if you have v15_id field) ---
    #             geo_name = geo.get('name') or ''
    #             existing = None
    #             if geo_name:
    #                 search_domain = [('name', '=', geo_name)]
    #                 if store_18_id:
    #                     search_domain.append(('store_id', '=', store_18_id))
    #                 existing = self.env['emp.geo_location'].search(search_domain, limit=1)

    #             if existing:
    #                 _logger.info("Remote geo id %s already exists in v18 (record id %s) - updating it.", remote_id, existing.id)
    #                 # update fields if you want (optional)
    #                 existing.write({
    #                     'street': geo.get('street') or '',
    #                     'street2': geo.get('street2') or '',
    #                     'city': geo.get('city') or '',
    #                     'zip': geo.get('zip') or '',
    #                     'state_id': state_18_id,
    #                     'country_id': country_18_id,
    #                     'store_id': store_18_id,
    #                 })
    #                 geo_loc = existing
    #             else:
    #                 # create new
    #                 geo_loc = self.env['emp.geo_location'].create({
    #                     'name': geo_name,
    #                     'store_id': store_18_id,
    #                     'street': geo.get('street') or '',
    #                     'street2': geo.get('street2') or '',
    #                     'city': geo.get('city') or '',
    #                     'zip': geo.get('zip') or '',
    #                     'state_id': state_18_id,
    #                     'country_id': country_18_id,
    #                     # Optionally store remote_id if you added a field for it:
    #                     # 'v15_id': remote_id,
    #                 })
    #                 _logger.info("Created emp.geo_location in v18 (id %s) from remote id %s", geo_loc.id, remote_id)

    #             # --- transfer areas and coordinate points ---
    #             area_ids_15 = geo.get('area_ids', [])
    #             if not area_ids_15:
    #                 _logger.info("No areas for remote geo id %s. Continuing.", remote_id)
    #                 continue

    #             areas_15 = models_15.execute_kw(
    #                 db, uid, password,
    #                 'geo_location.area', 'read',
    #                 [area_ids_15],
    #                 {'fields': ['name', 'coordinate_ids']}
    #             )

    #             for area in areas_15:
    #                 coord_ids_15 = area.get('coordinate_ids', [])
    #                 coords_15 = []
    #                 if coord_ids_15:
    #                     coords_15 = models_15.execute_kw(
    #                         db, uid, password,
    #                         'area.coordinate', 'read',
    #                         [coord_ids_15],
    #                         {'fields': ['x', 'y']}
    #                     )

    #                 coord_18_ids = []
    #                 for coord in coords_15:
    #                     x = coord.get('x')
    #                     y = coord.get('y')
    #                     # skip invalid coords
    #                     if x is None or y is None:
    #                         continue
    #                     coord_obj = self.env['area.coordinate'].search([('x', '=', x), ('y', '=', y)], limit=1)
    #                     if not coord_obj:
    #                         coord_obj = self.env['area.coordinate'].create({'x': x, 'y': y})
    #                     coord_18_ids.append(coord_obj.id)

    #                 # avoid duplicate area names under same geo by searching first
    #                 existing_area = self.env['geo_location.area'].search([('name', '=', area.get('name')), ('empgeo_id', '=', geo_loc.id)], limit=1)
    #                 if existing_area:
    #                     _logger.info("Area '%s' already exists under geo %s - updating coordinates.", area.get('name'), geo_loc.id)
    #                     existing_area.write({'coordinate_ids': [(6, 0, coord_18_ids)]})
    #                 else:
    #                     self.env['geo_location.area'].create({
    #                         'name': area.get('name'),
    #                         'coordinate_ids': [(6, 0, coord_18_ids)],
    #                         'empgeo_id': geo_loc.id,
    #                     })

    #             _logger.info("✅ Finished processing remote geo id %s", remote_id)

    #         except Exception as inner_e:
    #             _logger.exception("❌ Failed processing remote geo record %s: %s", geo.get('id'), inner_e)
    #             # continue to next record

    #     _logger.info("✅ Geo location sync completed successfully for requested IDs.")


    def sync_geo_location_data_remaining(self):
        _logger.info("\n\n==========APIIIII= CALLLLLL=======")
        url = 'http://192.168.29.162:8069/api/geo_location'
        # api_key = 'your_api_key_here'  # if required
        # response = requests.get(url, headers={'Authorization': f'Bearer {api_key}'}, timeout=30)
        response = requests.get(url, timeout=30)
        data = response.json().get('geo_locations', [])
        _logger.info("==========response========", response)
        _logger.info("==========data========", data)

        for geo in data:
            store = self.env['store.store'].search([('name','=',geo.get('store'))], limit=1)
            if not store and geo.get('store'):
                store = self.env['store.store'].create({'name': geo.get('store')})

            country = self.env['res.country'].search([('name','ilike',geo.get('country'))], limit=1)
            state = self.env['res.country.state'].search([('name','=',geo.get('state')), ('country_id','=',country.id if country else False)], limit=1) if geo.get('state') else False

            # Avoid duplicates
            existing = self.env['emp.geo_location'].search([('name','=',geo.get('name')), ('store_id','=',store.id if store else False)], limit=1)
            vals = {
                'name': geo.get('name'),
                'store_id': store.id if store else False,
                'street': geo.get('street'),
                'street2': geo.get('street2'),
                'city': geo.get('city'),
                'zip': geo.get('zip'),
                'country_id': country.id if country else False,
                'state_id': state.id if state else False,
            }

            if existing:
                existing.write(vals)
            else:
                record = self.env['emp.geo_location'].create(vals)

            # Areas
            for area in geo.get('areas', []):
                coord_ids = []
                for c in area.get('coordinates', []):
                    coord = self.env['area.coordinate'].search([('x','=',c['x']), ('y','=',c['y'])], limit=1)
                    if not coord:
                        coord = self.env['area.coordinate'].create({'x':c['x'],'y':c['y']})
                    coord_ids.append(coord.id)

                existing_area = self.env['geo_location.area'].search([('name','=',area.get('name')), ('empgeo_id','=',existing.id if existing else record.id)], limit=1)
                if existing_area:
                    existing_area.write({'coordinate_ids': [(6,0,coord_ids)]})
                else:
                    self.env['geo_location.area'].create({
                        'name': area.get('name'),
                        'coordinate_ids': [(6,0,coord_ids)],
                        'empgeo_id': existing.id if existing else record.id
                    })
        _logger.info("✅ Fetched and synced geo locations from v15 successfully.")


    # employee data start
    @api.model
    def sync_hr_employee_data(self):
        url = 'https://jbmenterprisellc.com'
        db = 'Subway_with_5_stores'
        username = 'admin'
        password = 'Bot#753'

        try:
            common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", allow_none=True)
            uid = common.authenticate(db, username, password, {})
            if not uid:
                _logger.error("❌ Authentication failed to Odoo 15.")
                return
            models_15 = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", allow_none=True)
        except Exception as e:
            _logger.exception("Failed to connect/authenticate to Odoo15: %s", e)
            return

        read_fields = [
            'active', 'name', 'middle_name', 'last_name', 'ssn_no', 'address', 'address_line_2',
            'city', 'state', 'postal_zip_code', 'country', 'date_of_birth',
            'email_id', 'gender', 'tz', 'cell_no_1', 'cell_no_2', 'cell_no_3',
            'last_lat', 'last_lng', 'employee_access_ids', 'legal_entity_name',
            'franchise_name', 'per_hr_wage', 'hired_date', 'employment_type',
            'filing_status', 'no_of_dependents_claimed_in_form_w4_line_5',
            'terms_and_conditions', 'type_of_compensation'
        ]

        try:
            employee_ids_15 = models_15.execute_kw(
                db, uid, password,
                'hr.employee', 'search', [[]],
                {'context': {'active_test': False}}
            )
            employees_15 = models_15.execute_kw(
                db, uid, password,
                'hr.employee', 'read',
                [employee_ids_15],
                {'fields': read_fields}
            )
            _logger.info("✅ Found %s employees in Odoo15", len(employees_15))
        except Exception as e:
            _logger.exception("Failed to fetch hr.employee from Odoo15: %s", e)
            return

        created_count = 0

        for emp in employees_15:
            with self.env.cr.savepoint():
                try:
                    country_18_id = False
                    country_15 = emp.get('country')
                    if country_15 and isinstance(country_15, (list, tuple)) and len(country_15) > 1:
                        country_name = country_15[1] or ''
                        if country_name:
                            country = self.env['res.country'].search(
                                [('name', 'ilike', country_name.strip())], limit=1
                            )
                            if country:
                                country_18_id = country.id

                    state_18_id = False
                    state_15 = emp.get('state')
                    if state_15:
                        state_name_15 = self.normalize_state_name(
                            state_15[1] if isinstance(state_15, (list, tuple)) else state_15
                        )
                        if state_name_15:
                            domain = [('name', '=', state_name_15)]
                            if country_18_id:
                                domain.append(('country_id', '=', country_18_id))
                            state = self.env['res.country.state'].search(domain, limit=1)
                            if state:
                                state_18_id = state.id

                    vals = {
                        'active': emp.get('active', True),
                        'first_name': emp.get('name'),
                        'middle_name': emp.get('middle_name'),
                        'last_name': emp.get('last_name'),
                        'ssn_no': emp.get('ssn_no'),
                        'address': emp.get('address'),
                        'address_line_2': emp.get('address_line_2'),
                        'city': emp.get('city'),
                        'state': state_18_id or False,
                        'postal_zip_code': emp.get('postal_zip_code'),
                        'country': country_18_id or False,
                        'date_of_birth': emp.get('date_of_birth'),
                        'email_id': emp.get('email_id'),
                        'gender': emp.get('gender') or False,
                        'tz': emp.get('tz'),
                        'cell_no_1': emp.get('cell_no_1'),
                        'cell_no_2': emp.get('cell_no_2'),
                        'cell_no_3': emp.get('cell_no_3'),
                        'last_lat': emp.get('last_lat'),
                        'last_lng': emp.get('last_lng'),
                        'type_of_compensation': emp.get('type_of_compensation'),
                        'legal_entity_name': emp.get('legal_entity_name'),
                        'franchise_name': emp.get('franchise_name'),
                        'per_hr_wage': emp.get('per_hr_wage'),
                        'hired_date': emp.get('hired_date'),
                        'employment_type': emp.get('employment_type'),
                        'filing_status': emp.get('filing_status'),
                        'no_of_dependents_claimed_in_form_w4_line_5': emp.get('no_of_dependents_claimed_in_form_w4_line_5'),
                        'terms_and_conditions': emp.get('terms_and_conditions'),
                    }

                    new_emp = self.env['hr.employee'].create(vals)
                    created_count += 1

                    access_ids_15 = emp.get('employee_access_ids') or []
                    if access_ids_15:
                        try:
                            access_records_15 = models_15.execute_kw(
                                db, uid, password, 'emp.access', 'read',
                                [access_ids_15], {'fields': ['access_role', 'store_ids']}
                            )
                            for access in access_records_15:
                                role = access.get('access_role')
                                store_ids_15 = access.get('store_ids') or []
                                store_18_ids = []
                                if store_ids_15:
                                    stores_15 = models_15.execute_kw(
                                        db, uid, password, 'store.store', 'read',
                                        [store_ids_15], {'fields': ['name']}
                                    )
                                    for store in stores_15:
                                        store_name = store.get('name')
                                        if not store_name:
                                            continue
                                        store_18 = self.env['store.store'].search([('name', '=', store_name)], limit=1)
                                        if not store_18:
                                            store_18 = self.env['store.store'].create({'name': store_name})
                                        store_18_ids.append(store_18.id)
                                if role:
                                    self.env['emp.access'].create({
                                        'employee_id': new_emp.id,
                                        'access_role': role,
                                        'store_ids': [(6, 0, store_18_ids)],
                                    })
                        except Exception:
                            _logger.exception("⚠️ Could not fetch access for employee %s", emp.get('name'))

                except Exception as e:
                    _logger.exception("❌ Error creating employee %s (id:%s): %s",
                                      emp.get('name'), emp.get('id'), e)

        _logger.info(
            "🔄 HR Employee sync completed. Created:%s Total v15:%s Total v18:%s at %s",
            created_count,
            len(employees_15),
            self.env['hr.employee'].search_count([]),
            datetime.now()
        )