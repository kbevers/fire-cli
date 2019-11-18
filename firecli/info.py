import datetime
import sys
import itertools

import click
from sqlalchemy.orm import aliased
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import or_

import firecli
from firecli import firedb
from fireapi.model import Punkt, PunktInformation, PunktInformationType, Srid


@click.group()
def info():
    """
    Information om objekter i FIRE
    """
    pass


def koordinat_linje(koord):
    """
    Konstruer koordinatoutput ud fra koordinatens dimensionalitet
    """
    meta = f"{koord.t.strftime('%Y-%m-%d %H:%M')}   {koord.srid.name:<15.15}"

    dimensioner = 0
    if koord.x is not None and koord.y is not None:
        dimensioner = 2

    if koord.z is not None:
        if dimensioner == 2:
            dimensioner = 3
        else:
            dimensioner = 1

    if dimensioner == 1:
        linje = meta + f"{koord.z} ({koord.sz})"

    if dimensioner == 2:
        linje = meta + f"{koord.x:.9}, {koord.y:.9} ({koord.sx}, {koord.sy})"

    if dimensioner == 3:
        linje = meta + f"{koord.x:.9}, {koord.y:.9}, {koord.z:.7}"
        linje += f"  ({koord.sx}, {koord.sy}, {koord.sz})"

    return linje


def punkt_rapport(punkt: Punkt, ident: str, i: int, n: int) -> None:
    """
    Rapportgenerator for funktionen 'punkt' nedenfor.
    """
    firecli.print("")
    firecli.print("-" * 80)
    firecli.print(f" PUNKT {ident} ({i}/{n})", bold=True)
    firecli.print("-" * 80)
    firecli.print(f"  FIRE ID             :  {punkt.id}")
    firecli.print(f"  Oprettelsesdato     :  {punkt.registreringfra}")
    firecli.print("")

    firecli.print("--- PUNKTINFO ---", bold=True)
    for info in punkt.punktinformationer:
        if info.registreringtil is not None:
            continue
        tekst = info.tekst or ""
        # efter mellemrum rykkes teksten ind på linje med resten af
        # attributteksten
        tekst = tekst.replace("\n", "\n" + " " * 25).replace("\r", "")
        tal = info.tal or ""
        firecli.print(f"  {info.infotype.name:20}:  {tekst}{tal}")
    firecli.print("")

    firecli.print("--- GEOMETRI ---", bold=True)
    for geometriobjekt in punkt.geometriobjekter:
        firecli.print(f"  {geometriobjekt.geometri}")
        firecli.print("")

    firecli.print("--- KOORDINATER ---", bold=True)
    punkt.koordinater.sort(
        key=lambda x: (x.srid.name, x.t.strftime("%Y-%m-%dT%H:%M")), reverse=True
    )
    for koord in punkt.koordinater:
        if koord.registreringtil is not None:
            firecli.print("  " + koordinat_linje(koord), fg="red")
        else:
            firecli.print("* " + koordinat_linje(koord), fg="green")
    firecli.print("")

    firecli.print("--- OBSERVATIONER ---", bold=True)
    n_obs_til = len(punkt.observationer_til)
    n_obs_fra = len(punkt.observationer_fra)
    firecli.print(f"  Antal observationer til:  {n_obs_til}")
    firecli.print(f"  Antal observationer fra:  {n_obs_fra}")

    if n_obs_fra + n_obs_til > 0:
        min_obs = datetime.datetime(9999, 12, 31)
        max_obs = datetime.datetime(1, 1, 1)
        for obs in itertools.chain(punkt.observationer_til, punkt.observationer_fra):
            if obs.registreringfra < min_obs:
                min_obs = obs.registreringfra
            if obs.registreringfra > max_obs:
                max_obs = obs.registreringfra

        firecli.print(f"  Ældste observation     :  {min_obs}")
        firecli.print(f"  Nyeste observation     :  {max_obs}")

    firecli.print("")


@info.command()
@firecli.default_options()
@click.argument("ident")
def punkt(ident: str, **kwargs) -> None:
    """
    Vis al tilgængelig information om et fikspunkt

    IDENT kan være enhver form for navn et punkt er kendt som, blandt andet
    GNSS stationsnummer, G.I.-nummer, refnr, landsnummer osv.

    Søgningen er versalfølsom.
    """
    pi = aliased(PunktInformation)
    pit = aliased(PunktInformationType)

    try:
        punktinfo = (
            firedb.session.query(pi)
            .filter(
                pit.name.startswith("IDENT:"),
                or_(
                    pi.tekst == ident,
                    pi.tekst.like(f"FO  %{ident}"),
                    pi.tekst.like(f"GL  %{ident}"),
                ),
            )
            .all()
        )
        n = len(punktinfo)
        if n == 0:
            raise NoResultFound

        for i in range(n):
            punkt_rapport(punktinfo[i].punkt, ident, i + 1, n)
    except NoResultFound:
        try:
            punkt = firedb.hent_punkt(ident)
        except NoResultFound:
            firecli.print(f"Error! {ident} not found!", fg="red", err=True)
            sys.exit(1)
        punkt_rapport(punkt, ident, 1, 1)


@info.command()
@firecli.default_options()
@click.argument("srid", required=False)
@click.option("-a", "--all", is_flag=True, help="Vis alle SRID'er")
def srid(srid: str, all: bool, **kwargs):
    """
    Information om et givent SRID (Spatial Reference ID).

    Returnerer en oversigt over en given SRIDs egenskaber.
    Hvis ingen SRID angives returneres en liste over SRID'er der ikke bruges
    til tidsserier. Tidsserie-SRID'er kan slås til med --all.

    Eksempler på SRID'er: EPSG:25832, DK:SYS34, TS:81013
    """
    if srid is not None:
        try:
            srid = firedb.hent_srid(srid)
            firecli.print(f" SRID        : {srid.name}")
            firecli.print(f" Beskrivelse : {srid.beskrivelse}")
            firecli.print(f" X           : {srid.x}")
            firecli.print(f" Y           : {srid.y}")
            firecli.print(f" Z           : {srid.z}")
        except NoResultFound:
            firecli.print(f"Error! {srid_name} not found!", fg="red", err=True)
            sys.exit(1)
    else:
        srider = []
        srider.extend(firedb.hent_srider(namespace="EPSG"))
        srider.extend(firedb.hent_srider(namespace="DK"))
        srider.extend(firedb.hent_srider(namespace="GL"))
        srider.extend(firedb.hent_srider(namespace="FO"))
        if all:
            srider.extend(firedb.hent_srider(namespace="TS"))

        firecli.print("--- SRID ---", bold=True)
        for srid in srider:
            firecli.print(f" {srid.name:15}:  {srid.beskrivelse}")


@info.command()
@firecli.default_options()
@click.argument("infotype")
def infotype(infotype: str, **kwargs):
    """
    Information om en punktinfotype.

    Eksempler på punktinfotyper: IDENT:GNSS, AFM:diverse, ATTR:beskrivelse
    """
    try:
        pit = firedb.hent_punktinformationtype(infotype)
        if pit is None:
            raise NoResultFound
    except NoResultFound:
        firecli.print(f"Error! {infotype} not found!", fg="red", err=True)
        sys.exit(1)

    firecli.print("--- PUNKTINFOTYPE ---", bold=True)
    firecli.print(f"  Name        :  {pit.name}")
    firecli.print(f"  Description :  {pit.beskrivelse}")
    firecli.print(f"  Type        :  {pit.anvendelse}")
