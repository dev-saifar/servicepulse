import click
from flask import Flask
from app import db
from .import_opening import import_opening_csv

def register_inventory_cli(app: Flask):
    @app.cli.command("inventory-import-opening")
    @click.argument("csv_path", type=click.Path(exists=True))
    def inventory_import_opening(csv_path):
        """Import opening stock CSV into per-bin locations (GRN moves)."""
        click.echo(f"Importing opening list from: {csv_path}")
        import_opening_csv(csv_path)
        click.echo("Done.")
import click
from flask import Flask
from decimal import Decimal
from app import db
from .services import create_move
from .models import Item, Location

def register_inventory_cli(app: Flask):
    @app.cli.command("inventory-import-opening")
    @click.argument("csv_path", type=click.Path(exists=True))
    def inventory_import_opening(csv_path):
        """Import opening stock CSV into per-bin locations (GRN moves)."""
        from .import_opening import import_opening_csv
        click.echo(f"Importing opening list from: {csv_path}")
        import_opening_csv(csv_path)
        click.echo("Done.")

    @app.cli.command("inventory-issue")
    @click.option("--sku", required=True)
    @click.option("--bin", "bin_code", required=True)
    @click.option("--qty", required=True, type=float)
    def inventory_issue(sku, bin_code, qty):
        """Issue stock from a bin."""
        it = Item.query.filter_by(sku=sku).first_or_404()
        loc = Location.query.filter_by(code=bin_code).first_or_404()
        mv = create_move(item_id=it.id, location_id=loc.id, mtype="Issue", qty=Decimal(qty))
        db.session.commit()
        click.echo(f"Issued {qty} {it.uom} of {sku} from {bin_code} (move #{mv.id}).")

    @app.cli.command("inventory-return")
    @click.option("--sku", required=True)
    @click.option("--bin", "bin_code", required=True)
    @click.option("--qty", required=True, type=float)
    def inventory_return(sku, bin_code, qty):
        """Return stock to a bin."""
        it = Item.query.filter_by(sku=sku).first_or_404()
        loc = Location.query.filter_by(code=bin_code).first_or_404()
        mv = create_move(item_id=it.id, location_id=loc.id, mtype="Return", qty=Decimal(qty))
        db.session.commit()
        click.echo(f"Returned {qty} {it.uom} to {sku} in {bin_code} (move #{mv.id}).")

    @app.cli.command("inventory-transfer")
    @click.option("--sku", required=True)
    @click.option("--from-bin", "from_bin", required=True)
    @click.option("--to-bin", "to_bin", required=True)
    @click.option("--qty", required=True, type=float)
    def inventory_transfer(sku, from_bin, to_bin, qty):
        """Transfer stock between bins."""
        from .services import transfer_between_bins
        it = Item.query.filter_by(sku=sku).first_or_404()
        src = Location.query.filter_by(code=from_bin).first_or_404()
        dst = Location.query.filter_by(code=to_bin).first_or_404()
        transfer_between_bins(item_id=it.id, from_location_id=src.id, to_location_id=dst.id, qty=Decimal(qty))
        db.session.commit()
        click.echo(f"Moved {qty} of {sku} from {from_bin} → {to_bin}.")
