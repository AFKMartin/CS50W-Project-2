from django.contrib.auth import authenticate, login, logout
from django.db import IntegrityError
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from .models import AuctionListing, Category, Watchlist

from .models import User

def index(request):
    active_listings = AuctionListing.objects.filter(is_active=True)

    watching = []    

    if request.user.is_authenticated:
        watching = AuctionListing.objects.filter(
            watchlisted_by__user=request.user
        )

    return render(request, "auctions/index.html", {
        "listings": active_listings,
        "watching": watching
    })



def login_view(request):
    if request.method == "POST":

        # Attempt to sign user in
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)

        # Check if authentication successful
        if user is not None:
            login(request, user)
            return HttpResponseRedirect(reverse("index"))
        else:
            return render(request, "auctions/login.html", {
                "message": "Invalid username and/or password."
            })
    else:
        return render(request, "auctions/login.html")


def logout_view(request):
    logout(request)
    return HttpResponseRedirect(reverse("index"))


def register(request):
    if request.method == "POST":
        username = request.POST["username"]
        email = request.POST["email"]

        # Ensure password matches confirmation
        password = request.POST["password"]
        confirmation = request.POST["confirmation"]
        if password != confirmation:
            return render(request, "auctions/register.html", {
                "message": "Passwords must match."
            })

        # Attempt to create new user
        try:
            user = User.objects.create_user(username, email, password)
            user.save()
        except IntegrityError:
            return render(request, "auctions/register.html", {
                "message": "Username already taken."
            })
        login(request, user)
        return HttpResponseRedirect(reverse("index"))
    else:
        return render(request, "auctions/register.html")

@login_required
def close_listing(request, listing_id):
    listing = get_object_or_404(AuctionListing, pk=listing_id)

    # Only owner can close the listing
    if listing.owner != request.user:
        return HttpResponse("Unauthorized", status=401)

    listing.is_active = False
    listing.save()

    return redirect("listing_detail", listing_id=listing_id)

def closed_listings(request):
    closed_auctions = AuctionListing.objects.filter(is_active=False) # Why the hell did I typo this
    return render(request, "auctions/closed_listings.html", {
        "listings": closed_auctions
    })

@login_required
def delete_listing(request, listing_id):
    listing = get_object_or_404(AuctionListing, pk=listing_id)

    # Only owner can delete
    if listing.owner != request.user:
        return HttpResponse("Unauthorized", status=401)

    listing.delete()
    return redirect("index")

@login_required
def create_listing(request):
    if request.method == "POST":
        title = request.POST["title"]
        description = request.POST["description"]
        starting_bid = request.POST["starting_bid"]
        image_url = request.POST.get("image_url")
        category_id = request.POST.get("category")

        category = Category.objects.get(pk=category_id) if category_id else None

        auction = AuctionListing(
            title=title,
            description=description,
            starting_bid=starting_bid,
            image_url=image_url,
            category=category,
            owner=request.user
        )
        auction.save()

        return HttpResponseRedirect(reverse("index"))
    
    else:
        categories = Category.objects.all()
        return render(request, "auctions/create_listing.html", {
            "categories": categories
        })
    
@login_required
def categories(request):
    categories = Category.objects.all()
    return render(request, "auctions/categories.html", {
        "categories": categories
    })

@login_required
def category_listings(request, category_id):
    watching = []
    if request.user.is_authenticated:
        watching = AuctionListing.objects.filter(watchlisted_by__user=request.user)
        
    category = Category.objects.get(id=category_id)
    listings = AuctionListing.objects.filter(category=category, is_active=True)
    
    return render(request, "auctions/category_listings.html", {
        "category": category,
        "listings": listings,
        "watching": watching
    })

@login_required
def watchlist(request):
    watched_listings = AuctionListing.objects.filter(
        watchlisted_by__user=request.user
    )

    return render(request, "auctions/watchlist.html", {
        "listings": watched_listings
    })


def listing_detail(request, listing_id):
    listing = get_object_or_404(AuctionListing, pk=listing_id)
    
    # Determine if the user is watching this listing
    is_watching = False
    if request.user.is_authenticated:
        is_watching = Watchlist.objects.filter(user=request.user, listing=listing).exists()

    return render(request, "auctions/listing_detail.html", {
        "listing": listing,
        "is_watching": is_watching
    })

@login_required
def toggle_watchlist(request, listing_id):
    listing = get_object_or_404(AuctionListing, id=listing_id)

    watch_entry, created = Watchlist.objects.get_or_create(
        user=request.user,
        listing=listing
    )

    if not created:
        watch_entry.delete()

    return HttpResponseRedirect(request.META.get("HTTP_REFERER", reverse("index")))

