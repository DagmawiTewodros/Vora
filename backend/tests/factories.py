import datetime
from decimal import Decimal

from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.models import ExchangeRate, HotelSettings, Staff
from apps.guests.models import Guest
from apps.pos.models import MenuItem, Outlet
from apps.rooms.models import RatePlan, Room, RoomType

TODAY = datetime.date(2026, 11, 2)


def day(offset):
    return TODAY + datetime.timedelta(days=offset)


def setup_hotel(rooms_per_type=2):
    hotel = HotelSettings.load()
    hotel.business_date = TODAY
    hotel.tin = "0012345678"
    hotel.save()
    ExchangeRate.objects.create(date=TODAY - datetime.timedelta(days=10), usd_to_etb=Decimal("150.0000"))
    std = RoomType.objects.create(name="Standard Double", code="STD", capacity=2, base_rate_etb=5000, base_rate_usd=60)
    dlx = RoomType.objects.create(name="Deluxe King", code="DLX", capacity=3, base_rate_etb=7000, base_rate_usd=85)
    RatePlan.objects.create(name="Bed & Breakfast", code="BB", room_type=std, price_etb=6000, price_usd=70)
    RatePlan.objects.create(name="Bed & Breakfast", code="BB", room_type=dlx, price_etb=8000, price_usd=95)
    for i in range(rooms_per_type):
        Room.objects.create(number=f"10{i + 1}", floor=1, room_type=std)
        Room.objects.create(number=f"20{i + 1}", floor=2, room_type=dlx)
    return std, dlx


def staff(username="manager", role="manager", **extra):
    user = Staff.objects.create_user(username=username, password="pass-12345", role=role, **extra)
    return user


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def guest(**extra):
    data = {"first_name": "Abebe", "last_name": "Kebede", "nationality": "Ethiopia", "id_type": "fayda", "id_number": "FAY123"}
    data.update(extra)
    return Guest.objects.create(**data)


def foreign_guest(**extra):
    data = {"first_name": "Jane", "last_name": "Doe", "nationality": "United Kingdom", "id_type": "passport",
            "id_number": "GB998877", "visa_number": "ETV-1"}
    data.update(extra)
    return Guest.objects.create(**data)


def menu():
    restaurant = Outlet.objects.create(name="Restaurant", kind="restaurant")
    bar = Outlet.objects.create(name="Bar", kind="bar", has_kitchen=False)
    tibs = MenuItem.objects.create(name="Beef tibs", name_am="ጥብስ", price=Decimal("450.00"))
    tibs.outlets.add(restaurant)
    beer = MenuItem.objects.create(name="St. George beer", price=Decimal("120.00"), goes_to_kitchen=False)
    beer.outlets.add(restaurant, bar)
    return restaurant, bar, tibs, beer


def now():
    return timezone.now()
